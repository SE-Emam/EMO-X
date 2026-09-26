"""EMO-X realworld suite: mini-real software tasks (stdlib only).

SWE-bench measures real GitHub issues; EMO measures agent capabilities.
This suite bridges the gap with small but REAL tasks: an actual repo
fixture with a genuine bug class, real pytest verification, and the
full agent-loop trajectory (plan/observations/tool calls/failures/
recoveries/verification/termination). Not arithmetic toys: every
family fails for a reason a working engineer would recognize.

Families (each: fixture repo + failing tests + hidden oracle tests):
  RW1 off-by-one-pagination  classic fencepost in page slicing.
  RW2 config-key-mismatch     wrong dict key silently falls back.
  RW3 flaky-sort-stability    sort key ignores secondary ordering.

Mechanics reuse suites/agent-loop/episode.py tool primitives
(IMPORTED: Ctx, _safe not needed, tool_ls/tool_read/tool_run/
tool_edit, parse_tool_call via bench_lib) — same ls/read/run/edit
contract, same FINAL stop rule, same A1-A15 scoring shape. The oracle
is the held-out pytest suite: PASS iff fixture tests go green.

Raw records only (schema-valid per shared/schemas.py C4/C83).
No scoring here (X-3 owns it).
"""

import importlib.util
import json
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

from schemas import validate_attempt  # noqa: E402
from manifests import sha256_bytes, sha256_manifest  # noqa: E402

SUITE = "realworld"
FAMILY_IDS = ("RW1", "RW2", "RW3")
VARIANTS = ("canonical",)
AGENT_TEMP = 0.4
AGENT_MAX_STEPS = 15
AGENT_NUM_PREDICT = 800


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


# --- fixtures: real bug classes, real pytest ------------------------------

def _write(root, rel, content):
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)


def build_rw1(root):
    """Off-by-one pagination: page() drops the last item of each page."""
    _write(root, "pager/__init__.py", "")
    _write(root, "pager/core.py",
           "def page(items, number, size):\n"
           "    \"\"\"Return page `number` (1-based) of `size` items.\"\"\"\n"
           "    start = (number - 1) * size\n"
           "    return items[start:start + size - 1]\n")
    _write(root, "tests/test_pager.py",
           "from pager.core import page\n\n"
           "def test_first_page():\n"
           "    assert page([1, 2, 3, 4, 5], 1, 2) == [1, 2]\n\n"
           "def test_second_page():\n"
           "    assert page([1, 2, 3, 4, 5], 2, 2) == [3, 4]\n\n"
           "def test_partial_last():\n"
           "    assert page([1, 2, 3, 4, 5], 3, 2) == [5]\n")


def build_rw2(root):
    """Config-key mismatch: reader uses a stale key, silently defaults."""
    _write(root, "svc/__init__.py", "")
    _write(root, "svc/config.py", "TIMEOUT_S = 30\nRETRIES = 3\n")
    _write(root, "svc/client.py",
           "from svc import config\n\n"
           "def timeout():\n"
           "    \"\"\"Read the configured timeout (bug: stale key).\"\"\"\n"
           "    return getattr(config, 'TIMEOUT', 5)\n")
    _write(root, "tests/test_client.py",
           "from svc.client import timeout\n\n"
           "def test_timeout_matches_config():\n"
           "    assert timeout() == 30\n")


def build_rw3(root):
    """Unstable sort: secondary key ignored, ties come out arbitrary."""
    _write(root, "tasks/__init__.py", "")
    _write(root, "tasks/sched.py",
           "def order(jobs):\n"
           "    \"\"\"Sort by priority desc, then name asc.\"\"\"\n"
           "    return sorted(jobs, key=lambda j: -j[1])\n")
    _write(root, "tests/test_sched.py",
           "from tasks.sched import order\n\n"
           "def test_priority_first():\n"
           "    assert order([('b', 1), ('a', 2)]) == [('a', 2), ('b', 1)]\n\n"
           "def test_ties_by_name():\n"
           "    assert order([('b', 1), ('a', 1)]) == [('a', 1), ('b', 1)]\n")


BUILDERS = {"RW1": build_rw1, "RW2": build_rw2, "RW3": build_rw3}

TASKS = {
    "RW1": ("Pip-free repo. Run `python3 -m pytest tests/ -x -q`. "
            "The pager drops items. Inspect, locate the bug, fix source "
            "files, re-run tests until green. Do not stop early."),
    "RW2": ("Pip-free repo. Run `python3 -m pytest tests/ -x -q`. "
            "The client ignores configuration. Inspect, locate the bug, "
            "fix source files, re-run tests until green. Do not stop early."),
    "RW3": ("Pip-free repo. Run `python3 -m pytest tests/ -x -q`. "
            "Tied jobs come out unordered. Inspect, locate the bug, fix "
            "source files, re-run tests until green. Do not stop early."),
}

SYSTEM_FMT = (
    "You are a coding agent inside a repo at /repo. Fix the failing tests. "
    "Work ONLY with these tools, one call per message, exact format: %s"
    "EXACT parameter names: ls uses path; read uses path; run uses cmd; "
    "edit uses path+old+new.\n"
    "run allows only pytest/py_compile/ls/cat in /repo. "
    "edit fails if old not found verbatim.\n"
    "When tests pass, reply FINAL summary with NO tool call. "
    "Stop then.")
SYSTEM = SYSTEM_FMT % '<tool_call>\n<function=read>\n<parameter=path>pager/core.py</parameter>\n</function>\n</tool_call>\n'


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, capture_output=True)


def build_fixture(family, root):
    BUILDERS[family](root)
    _git(["init", "-q"], root)
    _git(["add", "-A"], root)
    _git(["-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "init"], root)


AGENT_TEMP = 0.4
AGENT_NUM_PREDICT = 800
AGENT_MAX_STEPS = 15


def run_rw_episode(family, chat, max_steps=AGENT_MAX_STEPS):
    """Run one realworld episode. Returns (result, trajectory).

    Same tool contract as the agent-loop (ls/read/run/edit + FINAL),
    driven by episode.py primitives (imported). Trajectory carries the
    SPEC P4 fields. The oracle is the fixture pytest suite going green.
    """
    ep = _load_episode()
    root = tempfile.mkdtemp(prefix="rwrepo_")
    build_fixture(family, root)
    ctx = ep.Ctx(root)
    history = [{"role": "system", "content": SYSTEM},
               {"role": "user", "content": TASKS[family]}]
    trajectory = {"plan": [TASKS[family]],
                  "observations": [],
                  "tool_calls": [],
                  "failures": [],
                  "recoveries": [],
                  "verification": [],
                  "termination": {}}
    steps, toks, lat = 0, 0, 0.0
    trace = []
    final = None
    try:
        while steps < max_steps:
            steps += 1
            try:
                text, dt, ev = chat(history, temp=AGENT_TEMP,
                                    think=True,
                                    num_predict=AGENT_NUM_PREDICT)
            except Exception as e:
                trace.append({"step": steps, "error": str(e)[:200]})
                trajectory["failures"].append(
                    {"step": steps, "kind": "BACKEND_ERROR",
                     "detail": str(e)[:200]})
                break
            lat += dt
            toks += ev if isinstance(ev, int) else 0
            fn, params = ep.parse_tool_call(text) if hasattr(
                ep, "parse_tool_call") else (None, {})
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
                        "kind": "FINAL", "step": steps, "summary": final}
                    break
                trace.append({"step": steps, "no_tool_call": text[:200]})
                trajectory["failures"].append(
                    {"step": steps, "kind": "FORMAT_ERROR",
                     "detail": "no tool call and no FINAL"})
                history.append({"role": "assistant", "content": text})
                history.append({"role": "user", "content":
                    "TOOLERR no tool call found. Call a tool or reply FINAL."})
                ctx.failed += 1
                continue
            ctx.calls += 1
            trace.append({"step": steps, "tool": fn,
                          "params": {k: v[:80] for k, v in params.items()}})
            trajectory["tool_calls"].append(
                {"step": steps, "tool": fn,
                 "params": {k: v[:80] for k, v in params.items()}})
            try:
                if fn == "ls":
                    ok, out = ep.tool_ls(params.get("path", "."), ctx)
                elif fn == "read":
                    ok, out = ep.tool_read(params.get("path", ""), ctx)
                elif fn == "run":
                    ok, out = ep.tool_run(params.get("cmd", ""), ctx)
                elif fn == "edit":
                    ok, out = ep.tool_edit(params.get("path", ""),
                                           params.get("old", "") or "",
                                           params.get("new", ""), ctx)
                else:
                    ok, out = False, "ERROR: unknown tool %s" % fn
            except Exception as e:
                ok, out = False, "ERROR: %s" % e
            trajectory["observations"].append(
                {"step": steps, "tool": fn, "ok": ok,
                 "output": out[-500:]})
            if not ok:
                ctx.failed += 1
                trajectory["failures"].append(
                    {"step": steps, "kind": "WRONG_TOOL",
                     "detail": out[:200]})
            else:
                if trajectory["failures"]:
                    trajectory["recoveries"].append(
                        {"step": steps, "after": "tool ok following failure"})
            history.append({"role": "assistant", "content": text})
            history.append({"role": "user", "content":
                            "TOOLRESP %s" % out})
        else:
            trajectory["termination"] = {"kind": "MAX_STEPS", "step": steps,
                                         "summary": None}
    finally:
        p = subprocess.run(["python3", "-m", "pytest", "tests/", "-q"],
                           cwd=root, capture_output=True, text=True,
                           timeout=120)
        tests_green = p.returncode == 0
        diff = subprocess.run(["git", "diff", "--name-only"], cwd=root,
                              capture_output=True, text=True).stdout.split()
        result = {
            "success": bool(tests_green and final),
            "tests_green": tests_green,
            "stopped_cleanly": final is not None,
            "tool_calls": ctx.calls,
            "failed_calls": ctx.failed,
            "files_read": sorted(set(ctx.reads)),
            "files_edited": sorted(ctx.edited),
            "diff_files": diff,
            "total_tokens": toks,
            "total_latency_s": round(lat, 1),
            "pytest": (p.stdout + p.stderr)[-600:],
            "trace": trace,
            "final": final,
            "trajectory": trajectory,
        }
        shutil.rmtree(root, ignore_errors=True)
    return result, trajectory


def load_manifest(family):
    """Load suites/realworld/manifests/<family>.json."""
    path = os.path.join(HERE, "manifests", "%s.json" % family)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def prompt_pack_sha256():
    """SHA256 over task prompts (B58 prompt hash input)."""
    blob = SYSTEM + "\n".join(TASKS[f] for f in FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    """SHA256 of this executor file's bytes (B58 harness hash input)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())


def run_family(family, chat, run_id, model_id, trial_id=1, index=1,
               seed=0, manifest=None, variant=None, max_steps=None):
    """Run one realworld family. Returns (attempt, response), schema-valid.

    variant other than None/"canonical" raises TypeError (NA, DEN).
    """
    v = variant or "canonical"
    if v != "canonical":
        raise TypeError("variant %r not supported for family %r"
                        % (v, family))
    if family not in FAMILY_IDS:
        raise KeyError("unknown realworld family: %r" % (family,))
    result, trajectory = run_rw_episode(
        family, chat, max_steps=max_steps or AGENT_MAX_STEPS)
    passed = bool(result.get("success"))
    status = "PASS" if passed else "FAIL"
    attempt = validate_attempt({
        "run_id": run_id, "model_id": model_id,
        "task_family_id": family,
        "instance_id": "%s-canonical-%03d" % (family, index),
        "variant_class": "canonical", "trial_id": trial_id,
        "primary_status": status, "score": 1.0 if passed else 0.0,
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
        "log": str(result.get("pytest", ""))[:500],
        "sample": str(result.get("final", ""))[:600],
        "manifest_sha256": sha256_manifest(
            manifest or load_manifest(family)),
    })
    response = {"instance_id": attempt["instance_id"],
                "trial_id": trial_id,
                "task": TASKS[family],
                "trajectory": trajectory,
                "trace": result.get("trace", []),
                "usage": {"tokens": result.get("total_tokens", 0)},
                "human_minutes": {"RW1": 12, "RW2": 8, "RW3": 10}[family]}
    return attempt, response
