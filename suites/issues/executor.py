"""EMO-X issues executor: issue episodes + held-out oracle (stdlib only).

Each episode presents the GitHub-issue-style report as the task, runs
the standard ls/read/run/edit + FINAL loop (episode.py primitives,
imported — never copied), then verifies with BOTH the visible fixture
tests and the held-out hidden tests. The hidden tests are written into
the repo only after the agent stops, executed, then removed: the agent
can never see them, so memorized fixture-green patches that break
general behavior still fail.

Oracle (SWE-bench-shaped): PASS iff fixture tests green AND hidden
tests green AND FINAL stop. Raw records only, schema-valid
(C4/C83). No scoring here.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
AGENTLOOP = os.path.join(ROOT, "suites", "agent-loop")
for _p in (HERE, ROOT, SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import contextlib

import sandbox  # noqa: E402
from manifests import sha256_bytes, sha256_manifest  # noqa: E402
from schemas import validate_attempt  # noqa: E402


def _load_cases():
    """Load sibling cases.py by path (never bare `import cases`).

    Bare imports pollute sys.modules['cases'] and break consumers
    (e.g. tests/backends/test_suites.py) that expect code-bench-25's
    module under that name.
    """
    path = os.path.join(HERE, "cases.py")
    name = "emox_issues_cases"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_cases = _load_cases()
SUITE = _cases.SUITE
FAMILY_IDS = _cases.FAMILY_IDS
VARIANTS = _cases.VARIANTS
ISSUES = _cases.ISSUES
FIXTURES = _cases.FIXTURES
HIDDEN_TESTS = _cases.HIDDEN_TESTS
issue_text = _cases.issue_text
load_manifest = _cases.load_manifest

AGENT_TEMP = 0.4
AGENT_NUM_PREDICT = 800
AGENT_MAX_STEPS = 15

SYSTEM_FMT = (
    "You are a coding agent inside a repo at /repo. Fix the reported issue. "
    "Work ONLY with these tools, one call per message, exact format: %s"
    "EXACT parameter names: ls uses path; read uses path; run uses cmd; "
    "edit uses path+old+new.\n"
    "run allows only pytest/py_compile/ls/cat in /repo. "
    "edit fails if old not found verbatim.\n"
    "When tests pass, reply FINAL summary with NO tool call. "
    "Stop then."
)
SYSTEM_EXAMPLE = {
    "IS1": "csvmini/parser.py",
    "IS2": "cfgtools/merge.py",
    "IS3": "retry/backoff.py",
    "IS4": "urlx/join.py",
    "IS5": "retrybudget/budget.py",
    "IS6": "jschem/validate.py",
    "IS7": "seqtools/dedup.py",
    "IS8": "tzconv/convert.py",
    "IS9": "ttlcache/cache.py",
    "IS10": "units/convert.py",
    "IS11": "text/slug.py",
    "IS12": "batch/chunks.py",
    "IS13": "nest/flat.py",
    "IS14": "envcfg/get.py",
    "IS15": "ver/compare.py",
}
_HIDDEN_FILE = "test_hidden_oracle_emo.py"


def _load_episode():
    path = os.path.join(AGENTLOOP, "episode.py")
    name = "emox_agentloop_episode"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, capture_output=True)


def build_fixture(family, root):
    for rel, content in FIXTURES[family]().items():
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
    _git(["init", "-q"], root)
    _git(["add", "-A"], root)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], root)


def _system_for(family):
    example = SYSTEM_EXAMPLE[family]
    return SYSTEM_FMT % (
        f"<tool_call>\n<function=read>\n<parameter=path>{example}</parameter>\n"
        "</function>\n</tool_call>\n"
    )


def run_is_episode(family, chat, max_steps=AGENT_MAX_STEPS):
    """Run one issue episode. Returns (result, trajectory).

    Same tool contract as agent-loop/realworld; task text is the issue
    report. The oracle runs fixture tests, then writes the held-out
    hidden tests into the repo, runs them, and removes the file.
    """
    ep = _load_episode()
    root = tempfile.mkdtemp(prefix="isrepo_")
    build_fixture(family, root)
    ctx = ep.Ctx(root)
    task = issue_text(family)
    history = [
        {"role": "system", "content": _system_for(family)},
        {"role": "user", "content": task},
    ]
    trajectory = {
        "plan": [task],
        "observations": [],
        "tool_calls": [],
        "failures": [],
        "recoveries": [],
        "verification": [],
        "termination": {},
    }
    steps, toks, lat = 0, 0, 0.0
    trace = []
    final = None
    try:
        while steps < max_steps:
            steps += 1
            try:
                text, dt, ev = chat(
                    history, temp=AGENT_TEMP, think=True, num_predict=AGENT_NUM_PREDICT
                )
            except Exception as e:
                trace.append({"step": steps, "error": str(e)[:200]})
                trajectory["failures"].append(
                    {"step": steps, "kind": "BACKEND_ERROR", "detail": str(e)[:200]}
                )
                break
            lat += dt
            toks += ev if isinstance(ev, int) else 0
            fn, params = (
                ep.parse_tool_call(text)
                if hasattr(ep, "parse_tool_call")
                else (None, {})
            )
            if fn is None:
                try:
                    from bench_lib import parse_tool_call as _ptc

                    fn, params = _ptc(text)
                except Exception:
                    fn, params = None, {}
            if not fn:
                if "FINAL" in text:
                    final = text.strip()[:300]
                    trace.append({"step": steps, "final": final})
                    trajectory["termination"] = {
                        "kind": "FINAL",
                        "step": steps,
                        "summary": final,
                    }
                    break
                trace.append({"step": steps, "no_tool_call": text[:200]})
                trajectory["failures"].append(
                    {
                        "step": steps,
                        "kind": "FORMAT_ERROR",
                        "detail": "no tool call and no FINAL",
                    }
                )
                history.append({"role": "assistant", "content": text})
                history.append(
                    {
                        "role": "user",
                        "content": "TOOLERR no tool call found. Call a tool or reply FINAL.",
                    }
                )
                ctx.failed += 1
                continue
            ctx.calls += 1
            trace.append(
                {
                    "step": steps,
                    "tool": fn,
                    "params": {k: v[:80] for k, v in params.items()},
                }
            )
            trajectory["tool_calls"].append(
                {
                    "step": steps,
                    "tool": fn,
                    "params": {k: v[:80] for k, v in params.items()},
                }
            )
            try:
                if fn == "ls":
                    ok, out = ep.tool_ls(params.get("path", "."), ctx)
                elif fn == "read":
                    ok, out = ep.tool_read(params.get("path", ""), ctx)
                elif fn == "run":
                    ok, out = ep.tool_run(params.get("cmd", ""), ctx)
                elif fn == "edit":
                    ok, out = ep.tool_edit(
                        params.get("path", ""),
                        params.get("old", "") or "",
                        params.get("new", ""),
                        ctx,
                    )
                else:
                    ok, out = False, f"ERROR: unknown tool {fn}"
            except Exception as e:
                ok, out = False, f"ERROR: {e}"
            trajectory["observations"].append(
                {"step": steps, "tool": fn, "ok": ok, "output": out[-500:]}
            )
            if not ok:
                ctx.failed += 1
                trajectory["failures"].append(
                    {"step": steps, "kind": "WRONG_TOOL", "detail": out[:200]}
                )
            else:
                if trajectory["failures"]:
                    trajectory["recoveries"].append(
                        {"step": steps, "after": "tool ok following failure"}
                    )
            history.append({"role": "assistant", "content": text})
            history.append({"role": "user", "content": f"TOOLRESP {out}"})
        else:
            trajectory["termination"] = {
                "kind": "MAX_STEPS",
                "step": steps,
                "summary": None,
            }
    finally:
        test_rc, test_output = sandbox.run_in_sandbox(
            ["python3", "-m", "pytest", "tests/", "-q"], sandbox_dir=root, timeout=120
        )
        tests_green = test_rc == 0
        hidden_green, hidden_log = _run_hidden_tests(family, root)
        diff = subprocess.run(
            ["git", "diff", "--name-only"], cwd=root, capture_output=True, text=True
        ).stdout.split()
        result = {
            "success": bool(tests_green and hidden_green and final),
            "tests_green": tests_green,
            "hidden_green": hidden_green,
            "hidden_log": hidden_log,
            "stopped_cleanly": final is not None,
            "tool_calls": ctx.calls,
            "failed_calls": ctx.failed,
            "files_read": sorted(set(ctx.reads)),
            "files_edited": sorted(ctx.edited),
            "diff_files": diff,
            "total_tokens": toks,
            "total_latency_s": round(lat, 1),
            "pytest": test_output[-600:],
            "trace": trace,
            "final": final,
            "trajectory": trajectory,
        }
        shutil.rmtree(root, ignore_errors=True)
    return result, trajectory


def _run_hidden_tests(family, root):
    """Write held-out tests, run them, remove the file. Returns (ok, log)."""
    path = os.path.join(root, _HIDDEN_FILE)
    try:
        with open(path, "w") as f:
            f.write(HIDDEN_TESTS[family])
        rc, output = sandbox.run_in_sandbox(
            ["python3", "-m", "pytest", _HIDDEN_FILE, "-q"],
            sandbox_dir=root,
            timeout=120,
        )
        return rc == 0, output[-600:]
    except Exception as e:
        return False, f"hidden-oracle-error: {str(e)[:200]}"
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


def prompt_pack_sha256():
    """SHA256 over issue texts (B58 prompt hash input)."""
    blob = "\n".join(issue_text(f) for f in FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    """SHA256 of this executor file's bytes (B58 harness hash input)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())


def run_family(
    family,
    chat,
    run_id,
    model_id,
    trial_id=1,
    index=1,
    seed=0,
    manifest=None,
    variant=None,
    max_steps=None,
):
    """Run one issues family. Returns (attempt, response), schema-valid.

    variant other than None/"canonical" raises TypeError (NA, DEN).
    """
    v = variant or "canonical"
    if v != "canonical":
        raise TypeError(f"variant {v!r} not supported for family {family!r}")
    if family not in FAMILY_IDS:
        raise KeyError(f"unknown issues family: {family!r}")
    result, trajectory = run_is_episode(
        family, chat, max_steps=max_steps or AGENT_MAX_STEPS
    )
    passed = bool(result.get("success"))
    status = "PASS" if passed else "FAIL"
    attempt = validate_attempt(
        {
            "run_id": run_id,
            "model_id": model_id,
            "task_family_id": family,
            "instance_id": "%s-canonical-%03d" % (family, index),
            "variant_class": "canonical",
            "trial_id": trial_id,
            "primary_status": status,
            "score": 1.0 if passed else 0.0,
            "eligible_for_task_score": True,
            "eligible_for_pass_rate": True,
            "eligible_for_efficiency": True,
            "eligible_for_calibration": False,
            "primary_failure": None if passed else "WRONG_RESULT",
            "secondary_failure_tags": [],
            "seed": seed,
            "reasoning_mode": "provider_default",
            "scaffold_level": "L2-standard",
            "tool_calls": result.get("tool_calls", 0),
            "failed_calls": result.get("failed_calls", 0),
            "tests_green": result.get("tests_green", False),
            "hidden_green": result.get("hidden_green", False),
            "log": str(result.get("pytest", ""))[:500],
            "sample": str(result.get("final", ""))[:600],
            "manifest_sha256": sha256_manifest(manifest or load_manifest(family)),
        }
    )
    response = {
        "instance_id": attempt["instance_id"],
        "trial_id": trial_id,
        "task": issue_text(family),
        "trajectory": trajectory,
        "trace": result.get("trace", []),
        "usage": {"tokens": result.get("total_tokens", 0)},
        "human_minutes": {
            "IS1": 10,
            "IS2": 10,
            "IS3": 8,
            "IS4": 8,
            "IS5": 8,
            "IS6": 12,
            "IS7": 6,
            "IS8": 10,
            "IS9": 12,
            "IS10": 8,
            "IS11": 6,
            "IS12": 8,
            "IS13": 8,
            "IS14": 8,
            "IS15": 8,
        }[family],
    }
    return attempt, response
