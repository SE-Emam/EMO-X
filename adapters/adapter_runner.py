"""Adapter runner: one third-party episode on the shop/ fixture -> results/.

    python adapters/adapter_runner.py --adapter {opencode|pi|hermes} --model MODEL_ID [--out results/]
    python adapters/adapter_runner.py --adapter pi --model "google/gemini-x" --task-dir /tmp/shop1 --timeout 600

Task contract: same shop/ fixture as the Batch 4 loop (shared/run.py::
build_repo / run_agent_suite) — fix source files until pytest is green.
The third-party harness drives with its NATIVE prompt/tools/stop rule, so
every result embeds the full harness spec and is labeled NON-COMPARABLE
against shared/run.py agent-loop results (PLAN harness+model lesson).

Result persistence reuses shared/bench_lib.py::save_result (stdlib only,
no network; only local subprocess calls to the agent CLI, git, pytest).
Exit 0 = episode executed and recorded (even if tests stayed red; the
record carries the verdict). Exit 2 = infrastructure error (unknown
adapter, missing CLI binary, unusable task dir) with a clear stderr message.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
import tempfile

ADAPTERS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ADAPTERS_DIR)
SHARED_DIR = os.path.join(ROOT, "shared")
for _p in (ADAPTERS_DIR, SHARED_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_lib as L  # noqa: E402  (reuses save_result result writer)
from _log import configure, get_logger  # noqa: E402  (P1-02 stdlib logging)

log = get_logger("adapter_runner")

ADAPTERS = ("opencode", "pi", "hermes")


def _load_adapter(name):
    if name == "opencode":
        import opencode_adapter as mod
    elif name == "hermes":
        import hermes_adapter as mod
    elif name == "pi":
        import pi_adapter as mod
    else:
        raise RuntimeError("unknown adapter %r (choose from %s)"
                           % (name, "/".join(ADAPTERS)))
    return mod


def _fresh_task_dir():
    """Materialize the Batch-4 shop/ fixture (shared/run.py::build_repo)."""
    import run as run_mod
    task_dir = tempfile.mkdtemp(prefix="adapter_shop_")
    run_mod.build_repo(task_dir)
    return task_dir


def _verify_tests(task_dir):
    """Post-episode pytest check. Returns (tests_green, pytest_tail)."""
    try:
        p = subprocess.run(["python3", "-m", "pytest", "shop/tests/", "-q"],
                           cwd=task_dir, capture_output=True, text=True,
                           timeout=120)
        return bool(p.returncode == 0), (p.stdout + p.stderr)[-600:]
    except Exception as e:  # noqa: BLE001 - verification must not crash the run
        return False, "verify failed: %s" % e


def run_once(adapter_name, model_id, task_dir, timeout_s):
    mod = _load_adapter(adapter_name)
    trace = mod.run_episode(task_dir, model_id, timeout_s)
    tests_green, pytest_tail = _verify_tests(task_dir)
    record = {
        "adapter": adapter_name,
        "model": model_id,
        "task": "shop/ (Batch-4 fixture: fix source until pytest green)",
        "prompt_pack": "v1-reference-only",
        "harness": trace.get("harness"),
        "steps_n": len(trace.get("steps", [])),
        "trace": trace,
        "tests_green": tests_green,
        "pytest": pytest_tail,
        "success": bool(tests_green and trace.get("stopped_cleanly")),
        "comparability": trace.get("comparability"),
        "task_dir": task_dir,
    }
    return record


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run one third-party adapter episode")
    ap.add_argument("--adapter", required=True, choices=list(ADAPTERS))
    ap.add_argument("--model", required=True,
                    help="model id passed through (opencode: provider/model; pi: pattern)")
    ap.add_argument("--out", default=os.path.join(ROOT, "results") + os.sep)
    ap.add_argument("--task-dir", default=None,
                    help="existing shop/ fixture dir (default: build a fresh one)")
    ap.add_argument("--timeout", type=int, default=600,
                    help="wall-clock budget per episode in seconds")
    args = ap.parse_args(argv)

    task_dir = args.task_dir or _fresh_task_dir()
    configure()
    if not os.path.isdir(task_dir):
        log.warning("adapter_runner error: task_dir does not exist: %s"
                    % task_dir)
        return 2
    try:
        record = run_once(args.adapter, args.model, task_dir, args.timeout)
    except RuntimeError as e:
        log.warning("adapter_runner error: %s" % e)
        return 2

    os.makedirs(args.out, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.model)
    path = os.path.join(args.out, "adapter-%s_%s_%s.json"
                        % (args.adapter, slug, stamp))
    L.save_result(path, "agent-loop-%s" % args.adapter, record)
    log.info("adapter=%s model=%s tests_green=%s stopped_cleanly=%s" % (
        args.adapter, args.model, record["tests_green"],
        record["trace"].get("stopped_cleanly")))
    log.info("task_dir=%s" % task_dir)
    log.info("saved %s" % path)
    log.info("NOTE: %s" % record["comparability"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
