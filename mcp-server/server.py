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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SHARED = os.path.join(ROOT, "shared")
for _p in (SHARED, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import runner  # noqa: E402
from backends import make_chat  # noqa: E402

SERVER_NAME = "emo-x"
SERVER_VERSION = "2.0.0"


def _chat_from_params(params):
    """Build a chat callable from tool params (or env defaults)."""
    backend = params.get("backend") or os.environ.get("BACKEND", "stub")
    if str(backend).lower() == "stub":
        return runner.stub_chat_factory("mcp-smoke"), "stub-model", "stub"
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
    return runner.health_snapshot(params.get("out_root"))


def _tool_run_suite(params):
    suite = params.get("suite")
    if not suite:
        raise ValueError("suite is required")
    chat, model, backend = _chat_from_params(params)
    rundir, summary = runner.run_suite(
        suite, chat,
        model_id=params.get("model_id") or model,
        backend=params.get("backend") or backend,
        seed=int(params.get("seed", 0)),
        instances=int(params.get("instances", 1)),
        trials=int(params.get("trials", 1)),
        fault_rate=float(params.get("fault_rate", 0.25)),
        out_root=params.get("out_root"),
        families=params.get("families"),
        provider_profile=params.get("provider_profile"),
        scope=params.get("scope"),
        sampling=params.get("sampling"),
    )
    return dict(summary, run_dir=rundir)


def _tool_run_profile(params):
    chat, model, backend = _chat_from_params(params)
    runs, report = runner.run_profile(
        chat,
        model_id=params.get("model_id") or model,
        backend=params.get("backend") or backend,
        seed=int(params.get("seed", 0)),
        instances=int(params.get("instances", 1)),
        trials=int(params.get("trials", 1)),
        fault_rate=float(params.get("fault_rate", 0.25)),
        out_root=params.get("out_root"),
        provider_profile=params.get("provider_profile"),
        scope=params.get("scope"),
        sampling=params.get("sampling"),
    )
    return {"runs": runs, "report": report}


def _load_run_bundle(run_dir):
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
    outdir = params.get("out_dir") or (
        rundirs[0].rstrip("/") + "-report")
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
    manifest_a, attempts_a = _load_run_bundle(run_a)
    manifest_b, attempts_b = _load_run_bundle(run_b)
    comp = compare_models(
        attempts_a, attempts_b,
        model_a=params.get("model_a") or manifest_a.get("model", "A"),
        model_b=params.get("model_b") or manifest_b.get("model", "B"),
        manifest_a=manifest_a, manifest_b=manifest_b,
        B=int(params.get("B", 1000)),
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
                       "security S3-S5 need scope approval (fail-closed).",
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
                "out_root": {"type": "string"}}},
    },
    "run_profile": {
        "fn": _tool_run_profile,
        "description": "Full capability profile across all suites "
                       "(profile + fingerprint + efficiency + uncertainty).",
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
        return _result(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME,
                           "version": SERVER_VERSION}})
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
        # redacted arguments (keys masked) for safe diagnosis.
        redacted = {k: ("***" if "key" in k.lower() else v)
                    for k, v in args.items()} if isinstance(args,
                                                             dict) else args
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
    rs = handle_message(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "run_suite",
                    "arguments": {"suite": "dynamic-code",
                                  "backend": "stub",
                                  "families": ["DC1"],
                                  "out_root": "/tmp/emox_mcp_smoke"}}})
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
    shutil.rmtree("/tmp/emox_mcp_smoke", ignore_errors=True)
    print("MCP smoke: tools=%s self_test=PASS suite=PASS hidden-gate=PASS"
          % ",".join(names))


if __name__ == "__main__":
    if "--smoke" in sys.argv[1:]:
        smoke()
    else:
        serve_stdio()
