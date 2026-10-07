"""EMO-X MCP server (stdio, JSON-RPC 2.0). Stdlib only.

Exposes the benchmark to ANY MCP-capable coding agent (opencode, pi,
forge, codex, hermes-agent, open-web, AnythingLLM, ...): one server,
no per-agent adapter. The agent calls tools; this server runs
shared/runner.py in-process and returns JSON-serializable summaries.

Tools:
  self_test        SPEC 35 fail-closed harness check (14 checks + SKIP)
  health           benchmark-health snapshot over stored raw runs
  run_suite        one suite end-to-end -> sealed raw bundle (summary)
  run_profile      full capability profile across PROFILE_SUITES
  compare_models   interval-only comparison of two stored runs
                   (significant/directional/inconclusive — never "winner")

Fail-closed gates (never bypassed):
  - code25-hidden requires scope "hidden-ok" (else ScopeRequiredError,
    no bundle, no model call).
  - security S3-S5 require scope approval (else VOID/SAFETY_GATE).
  - run_suite refuses unknown suites (ValueError -> JSON-RPC error).

Model backends: the server builds chat via shared/backends.make_chat
from per-call params or env (BACKEND/BASE_URL/MODEL, OPENAI_*). No
credentials are ever logged or echoed back.

Protocol: newline-delimited JSON-RPC 2.0 on stdin/stdout
  -> {"jsonrpc":"2.0","id":1,"method":"tools/list"}
  -> {"jsonrpc":"2.0","id":2,"method":"tools/call",
      "params":{"name":"self_test","arguments":{}}}
Also answers initialize/initialized and notifications/* (no-op).

Usage:
  python3 mcp-server/server.py            # stdio mode (MCP clients)
  python3 mcp-server/server.py --smoke   # local self-check, no client
"""

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SHARED = os.path.join(ROOT, "shared")
for _p in (SHARED, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import runner  # noqa: E402
from backends import make_chat  # noqa: E402

SERVER_NAME = "emo-x"
# Single source of truth: benchmark version lives in shared/runner.py.
SERVER_VERSION = str(getattr(runner, "BENCHMARK_VERSION", "2.0.0-rc1"))


#: Backends an MCP client may request. `cli` executes a local binary
#: and is therefore gated separately (opt-in + allowlist, P0-1).
_MCP_SAFE_BACKENDS = frozenset(
    {"stub", "kaggle", "colab", "openai-generic", "openai"})


def _mcp_cli_allowlist():
    """Parse EMOX_MCP_CLI_ALLOWLIST (colon-separated absolute paths)."""
    raw = os.environ.get("EMOX_MCP_CLI_ALLOWLIST", "")
    entries = []
    for part in raw.split(":"):
        part = part.strip()
        if part:
            entries.append(os.path.realpath(part))
    return entries


def _validate_mcp_cli_binary(cli_bin):
    """Fail-closed validation for the cli backend binary over MCP (P0-1).

    Requires EMOX_MCP_ALLOW_CLI=1 and an explicit allowlist entry.
    Raises PermissionError otherwise.
    """
    if os.environ.get("EMOX_MCP_ALLOW_CLI") != "1":
        raise PermissionError(
            "cli backend is disabled over MCP; operator must set "
            "EMOX_MCP_ALLOW_CLI=1 and EMOX_MCP_CLI_ALLOWLIST to opt in")
    candidate = (cli_bin or os.environ.get("CLI_BIN")
                 or os.environ.get("BASE_URL") or "opencode")
    # Absolute-path only: never resolve via PATH for an agent-supplied name.
    if not os.path.isabs(str(candidate)):
        raise PermissionError(
            "cli binary must be an absolute allowlisted path: %r" % (candidate,))
    full = os.path.realpath(str(candidate))
    allow = _mcp_cli_allowlist()
    if not allow or full not in allow:
        raise PermissionError(
            "cli binary not in EMOX_MCP_CLI_ALLOWLIST: %r" % (candidate,))
    if not (os.path.isfile(full) and os.access(full, os.X_OK)):
        raise PermissionError(
            "cli binary not executable: %r" % (candidate,))
    return full


def _validate_mcp_model_id(model):
    """Bound the cli route id (argv element, no shell)."""
    text = str(model or "")
    if not text or len(text) > 200 or any(
            c in text for c in ("\x00", "\n", "\r")):
        raise ValueError("invalid model id over MCP")
    return text


def _chat_from_params(params):
    """Build a chat callable from tool params (or env defaults)."""
    backend = params.get("backend") or os.environ.get("BACKEND", "stub")
    if str(backend).lower() == "stub":
        return runner.stub_chat_factory("mcp-smoke"), "stub-model", "stub"
    if str(backend).lower() == "cli":
        # P0-1: local-binary execution via agent-controlled params.
        # Opt-in only: EMOX_MCP_ALLOW_CLI=1 + absolute allowlisted binary.
        cli_bin = _validate_mcp_cli_binary(params.get("base_url"))
        model = _validate_mcp_model_id(
            params.get("model") or os.environ.get("MODEL", "mcp-model"))
        chat = make_chat("cli", cli_bin, model, None)
        return chat, model, "cli"
    if str(backend).lower() not in _MCP_SAFE_BACKENDS:
        raise ValueError("backend not allowed over MCP: %r" % (backend,))
    chat = make_chat(
        backend,
        params.get("base_url"),
        params.get("model"),
        params.get("api_key") or os.environ.get("OPENAI_API_KEY"),
    )
    model = params.get("model") or os.environ.get("MODEL", "mcp-model")
    return chat, model, backend


def _tool_self_test(params):
    ok, rows = runner.run_self_test()
    return {"ok": ok,
            "checks": [{"name": n, "pass": bool(p), "detail": d}
                       for n, p, d in rows]}


def _tool_health(params):
    return runner.health_snapshot(_confine_out_root(params.get("out_root")))


def _progress_emitter(token):
    """Build an on_event callback emitting MCP progress notifications.

    Server-initiated notifications (no id) stream to stdout while the
    tool runs, so clients see suite/attempt progress instead of silence.
    """
    def emit(snapshot):
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/progress",
            "params": dict(snapshot, progressToken=token),
        }, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()
    return emit


def _tool_run_suite(params):
    suite = params.get("suite")
    if not suite:
        raise ValueError("suite is required")
    chat, model, backend = _chat_from_params(params)
    try:
        from progress import ProgressReporter
    except ImportError:
        from shared.progress import ProgressReporter
    token = params.get("progress_token")
    prog = ProgressReporter(
        enabled=False,
        on_event=_progress_emitter(token) if token else None)
    rundir, summary = runner.run_suite(
        suite, chat,
        model_id=params.get("model_id") or model,
        backend=params.get("backend") or backend,
        seed=int(params.get("seed", 0)),
        instances=min(int(params.get("instances", 1)), 100),
        trials=min(int(params.get("trials", 1)), 10),
        fault_rate=min(max(float(params.get("fault_rate", 0.25)), 0.0), 1.0),
        out_root=_confine_out_root(params.get("out_root")),
        families=params.get("families"),
        provider_profile=params.get("provider_profile"),
        scope=params.get("scope"),
        sampling=params.get("sampling"),
        progress=prog,
    )
    return dict(summary, run_dir=rundir)


def _tool_run_profile(params):
    chat, model, backend = _chat_from_params(params)
    try:
        from progress import ProgressReporter
    except ImportError:
        from shared.progress import ProgressReporter
    token = params.get("progress_token")
    prog = ProgressReporter(
        enabled=False,
        on_event=_progress_emitter(token) if token else None)
    runs, report = runner.run_profile(
        chat,
        model_id=params.get("model_id") or model,
        backend=params.get("backend") or backend,
        seed=int(params.get("seed", 0)),
        instances=min(int(params.get("instances", 1)), 100),
        trials=min(int(params.get("trials", 1)), 10),
        fault_rate=min(max(float(params.get("fault_rate", 0.25)), 0.0), 1.0),
        out_root=_confine_out_root(params.get("out_root")),
        provider_profile=params.get("provider_profile"),
        scope=params.get("scope"),
        sampling=params.get("sampling"),
        progress=prog,
    )
    return {"runs": runs, "report": report}


def _allowed_roots():
    """Directories an MCP client may point reads/writes at (audit SEC-2).

    Confinement roots: results/ and reports/ under the repo, plus the
    system temp dir (smoke runs), plus any path the operator explicitly
    set via EMOX_MCP_OUT_ROOT. The repo root itself is deliberately NOT
    a root: confinement must be narrow (P0-2). Everything else refused.
    """
    roots = [os.path.join(ROOT, "results"),
             os.path.join(ROOT, "reports"),
             tempfile.gettempdir()]
    extra = os.environ.get("EMOX_MCP_OUT_ROOT")
    if extra:
        roots.append(extra)
    return [os.path.realpath(r) for r in roots if r]


def _confine(path):
    """Canonicalize and confine a client-supplied path to allowed roots.

    Audit SEC-2: the MCP server must never read/write arbitrary host
    paths on behalf of an agent. Raises PermissionError otherwise.
    """
    if not isinstance(path, str) or not path:
        raise ValueError("path is required")
    full = os.path.realpath(path)
    for root in _allowed_roots():
        if full == root or os.path.commonpath([full, root]) == root:
            return full
    raise PermissionError("path outside allowed roots: %r" % (path,))


def _confine_out_root(path):
    """Confine an optional out_root (P0-2). None passes through (default).

    A supplied out_root is canonicalized against _allowed_roots exactly
    like run_dir/out_dir. Nonexistent-but-confined paths are allowed so
    the runner can create fresh RUN dirs; nothing outside the roots is.
    """
    if path is None:
        return None
    if isinstance(path, str) and not path.strip():
        raise ValueError("out_root must be a non-empty path")
    return _confine(path)


def _load_run_bundle(run_dir):
    run_dir = _confine(run_dir)
    try:
        from seal import require_seal
    except ImportError:
        from shared.seal import require_seal
    require_seal(run_dir)  # P0-6 fail-closed over MCP: no stats w/o seal.
    with open(os.path.join(run_dir, "manifest.json"),
              encoding="utf-8") as f:
        manifest = json.load(f)
    with open(os.path.join(run_dir, "events.jsonl"),
              encoding="utf-8") as f:
        attempts = [json.loads(l) for l in f if l.strip()]
    return manifest, attempts


def _tool_render_report(params):
    try:
        from render_report import render
        from render_leaderboard import render_board
    except ImportError:
        from shared.render_report import render
        from shared.render_leaderboard import render_board
    rundirs = params.get("run_dirs") or []
    if params.get("run_dir"):
        rundirs = [params["run_dir"]] + list(rundirs)
    if not rundirs:
        raise ValueError("run_dir (or run_dirs list) is required")
    rundirs = [_confine(d) for d in rundirs]
    outdir = params.get("out_dir") or (
        rundirs[0].rstrip("/") + "-report")
    outdir = _confine(outdir)
    if len(rundirs) == 1:
        render(rundirs[0], outdir)
        return {"mode": "single",
                "report_html": os.path.join(outdir, "report.html"),
                "report_json": os.path.join(outdir, "report.json")}
    render_board(rundirs, outdir)
    return {"mode": "leaderboard", "n_runs": len(rundirs),
            "report_html": os.path.join(outdir, "leaderboard.html"),
            "report_json": os.path.join(outdir, "leaderboard.json")}


def _tool_compare_models(params):
    try:
        from report_v2 import compare_models, render_comparison
    except ImportError:
        from shared.report_v2 import compare_models, render_comparison
    run_a = params.get("run_a")
    run_b = params.get("run_b")
    if not run_a or not run_b:
        raise ValueError("run_a and run_b (raw bundle dirs) are required")
    run_a, run_b = _confine(run_a), _confine(run_b)
    manifest_a, attempts_a = _load_run_bundle(run_a)
    manifest_b, attempts_b = _load_run_bundle(run_b)
    comp = compare_models(
        attempts_a, attempts_b,
        model_a=params.get("model_a") or manifest_a.get("model", "A"),
        model_b=params.get("model_b") or manifest_b.get("model", "B"),
        manifest_a=manifest_a, manifest_b=manifest_b,
        # Audit M: cap client-controlled bootstrap replicates (scoring
        # also enforces BOOTSTRAP_MAX=100k; the MCP default stays small).
        B=min(int(params.get("B", 1000)), 10000),
        seed=int(params.get("seed", 0)),
    )
    comp["rendered"] = render_comparison(comp)
    return comp


TOOLS = {
    "self_test": {
        "fn": _tool_self_test,
        "description": "Fail-closed harness check (14 checks + SKIP). "
                       "Run before any benchmark.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "health": {
        "fn": _tool_health,
        "description": "Benchmark-health snapshot (flakiness, saturation, "
                       "discrimination, contamination) over stored runs.",
        "inputSchema": {"type": "object",
                        "properties": {
                            "out_root": {"type": "string"}}},
    },
    "run_suite": {
        "fn": _tool_run_suite,
        "description": "Run one EMO-X suite end-to-end into a sealed raw "
                       "bundle. code25-hidden needs scope='hidden-ok'; "
                       "security S3-S5 need scope approval (fail-closed). "
                       "Pass progress_token to stream "
                       "notifications/progress while it runs.",
        "inputSchema": {
            "type": "object", "required": ["suite"],
            "properties": {
                "suite": {"type": "string"},
                "backend": {"type": "string"},
                "base_url": {"type": "string"},
                "model": {"type": "string"},
                "model_id": {"type": "string"},
                "seed": {"type": "integer"},
                "instances": {"type": "integer"},
                "trials": {"type": "integer"},
                "fault_rate": {"type": "number"},
                "provider_profile": {"type": "string"},
                "scope": {"type": "string"},
                "families": {"type": "array", "items": {"type": "string"}},
                "sampling": {"type": "object"},
                "progress_token": {"type": ["string", "integer"]},
                "out_root": {"type": "string"}}},
    },
    "run_profile": {
        "fn": _tool_run_profile,
        "description": "Full capability profile across all suites "
                       "(profile + fingerprint + efficiency + uncertainty). "
                       "Pass progress_token to stream "
                       "notifications/progress while it runs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "backend": {"type": "string"},
                "base_url": {"type": "string"},
                "model": {"type": "string"},
                "model_id": {"type": "string"},
                "seed": {"type": "integer"},
                "instances": {"type": "integer"},
                "trials": {"type": "integer"},
                "fault_rate": {"type": "number"},
                "provider_profile": {"type": "string"},
                "scope": {"type": "string"},
                "sampling": {"type": "object"},
                "out_root": {"type": "string"}}},
    },
    "compare_models": {
        "fn": _tool_compare_models,
        "description": "Interval-only comparison of two stored raw runs "
                       "(significant/directional/inconclusive). "
                       "NON_COMPARABLE runs are reported, never ranked.",
        "inputSchema": {
            "type": "object", "required": ["run_a", "run_b"],
            "properties": {
                "run_a": {"type": "string"},
                "run_b": {"type": "string"},
                "model_a": {"type": "string"},
                "model_b": {"type": "string"},
                "B": {"type": "integer"},
                "seed": {"type": "integer"}}},
    },
    "render_report": {
        "fn": _tool_render_report,
        "description": "Render one raw bundle (report.html) or N bundles "
                       "(leaderboard.html: table + chart + pairwise calls). "
                       "Open report_html in a browser. No network needed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_dir": {"type": "string"},
                "run_dirs": {"type": "array", "items": {"type": "string"}},
                "out_dir": {"type": "string"}}},
    },
}


#: Substrings marking a parameter as credential-bearing (case-insensitive).
#: Matched as substrings, except that "monkey"/"donkey" are stripped first
#: so words like "monkey" never count as containing "key".
_SENSITIVE_SUBSTRINGS = ("key", "secret", "token", "password", "passwd",
                          "cred", "authorization", "auth", "bearer")


def _is_sensitive_key(name):
    """True if a parameter name looks credential-bearing. Case-insensitive.

    "monkey"/"donkey" never match (they merely end in "key").
    """
    low = str(name).lower()
    stripped = low.replace("monkey", "").replace("donkey", "")
    return any(s in stripped for s in _SENSITIVE_SUBSTRINGS)


def _redact_args(args):
    """Return args with credential-bearing values replaced by '***'.

    Audit M: URL-valued params (base_url/out_root/...) are also
    stripped of embedded userinfo so `https://user:pass@host`
    never lands in error logs.
    """
    if not isinstance(args, dict):
        return args
    red = {}
    for k, v in args.items():
        if _is_sensitive_key(k):
            red[k] = "***"
        elif isinstance(v, str) and "://" in v and "@" in v:
            try:
                import urllib.parse as _up
                _parts = _up.urlsplit(v)
                _net = _parts.hostname or ""
                if _parts.port:
                    _net += ":%d" % _parts.port
                red[k] = _up.urlunsplit(
                    (_parts.scheme, _net, _parts.path or "",
                     _parts.query or "", ""))
            except Exception:
                red[k] = "***"
        else:
            red[k] = v
    return red


def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": str(message)[:500]}}


def handle_message(msg):
    """Handle one JSON-RPC message dict; return response dict or None."""
    if not isinstance(msg, dict):
        return _error(None, -32700, "parse error: not an object")
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}
    if method == "initialize":
        try:
            from splash import banner
        except ImportError:
            from shared.splash import banner
        try:
            splash_text = banner(width=80, color=False)
        except Exception:
            splash_text = "EMO-X"
        return _result(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME,
                           "version": SERVER_VERSION,
                           "splash": splash_text}})
    if method in ("initialized",) or str(method).startswith(
            "notifications/"):
        return None
    if method == "tools/list":
        return _result(req_id, {"tools": [
            {"name": n, "description": t["description"],
             "inputSchema": t["inputSchema"]}
            for n, t in TOOLS.items()]})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if tool is None:
            return _error(req_id, -32602, "unknown tool: %r" % (name,))
        # Redact credentials from any error surface: errors carry the
        # redacted arguments (credential values masked) for safe diagnosis.
        redacted = _redact_args(args)
        try:
            return _result(req_id, {"content": [
                {"type": "text",
                 "text": json.dumps(tool["fn"](args),
                                    ensure_ascii=False, default=str)}]})
        except (ValueError, PermissionError) as e:
            err = _error(req_id, -32602, "%s: %s" % (
                type(e).__name__, e))
            err["error"]["arguments"] = redacted
            return err
        except Exception as e:  # harness/model failure, not protocol error
            err = _error(req_id, -32000, "%s: %s" % (
                type(e).__name__, e))
            err["error"]["arguments"] = redacted
            return err
    return _error(req_id, -32601, "unknown method: %r" % (method,))


def serve_stdio():
    """Read newline-delimited JSON-RPC from stdin, write to stdout."""
    stdin, stdout = sys.stdin, sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            stdout.write(json.dumps(_error(None, -32700,
                                           "parse error")) + "\n")
            stdout.flush()
            continue
        resp = handle_message(msg)
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False,
                                    default=str) + "\n")
            stdout.flush()


def smoke():
    """Local self-check without a client: list + self_test + stub suite."""
    listed = handle_message({"jsonrpc": "2.0", "id": 1,
                             "method": "tools/list"})
    names = sorted(t["name"] for t in listed["result"]["tools"])
    assert names == ["compare_models", "health", "render_report",
                     "run_profile", "run_suite", "self_test"], names
    st = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                         "params": {"name": "self_test", "arguments": {}}})
    content = json.loads(st["result"]["content"][0]["text"])
    assert content["ok"] is True, content
    # P0-2: smoke out_root must itself satisfy confinement (tempdir root,
    # resolved — /tmp is a symlink on some platforms, so build it from
    # tempfile.gettempdir() rather than a hardcoded /tmp path).
    smoke_root = os.path.join(tempfile.gettempdir(), "emox_mcp_smoke")
    rs = handle_message(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "run_suite",
                    "arguments": {"suite": "dynamic-code",
                                  "backend": "stub",
                                  "families": ["DC1"],
                                  "out_root": smoke_root}}})
    assert "result" in rs, rs
    summary = json.loads(rs["result"]["content"][0]["text"])
    assert summary["n_attempts"] > 0, summary
    # Hidden gate must refuse without scope (fail-closed over MCP too).
    denied = handle_message(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "run_suite",
                    "arguments": {"suite": "code25-hidden",
                                  "backend": "stub"}}})
    assert "error" in denied, denied
    import shutil
    shutil.rmtree(smoke_root, ignore_errors=True)
    print("MCP smoke: tools=%s self_test=PASS suite=PASS hidden-gate=PASS"
          % ",".join(names))


if __name__ == "__main__":
    if "--smoke" in sys.argv[1:]:
        smoke()
    else:
        serve_stdio()
