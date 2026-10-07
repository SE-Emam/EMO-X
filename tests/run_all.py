"""Unified per-directory test runner for EMO-X (stdlib only).

Root cause (why NOT top-level ``unittest discover -s tests``):
  1. Test modules import top-level packages (e.g.
     ``from generators.task_dsl import ...``) which require the repo root
     on ``sys.path``; a bare discover from ``tests/`` raises
     ``ModuleNotFoundError`` (e.g. ``generators.task_dsl``).
  2. Two suites ship modules with identical basenames (notably the two
     ``cases.py``: ``suites/code-bench-25/cases.py`` vs
     ``suites/security/cases.py``). Loading both into one interpreter
     process collides in ``sys.modules``.

This runner works around both WITHOUT restructuring other agents' test
dirs (frozen): every test directory runs in its own isolated subprocess
with an explicit ``PYTHONPATH`` (repo root + ``shared/``), so imports
resolve and duplicate basenames never share a process.

Usage:
  python3 tests/run_all.py            # all suites, table + exit code
  python3 tests/run_all.py --suite scoring   # one suite only
  python3 tests/run_all.py --count    # print test-function counts only

  --count is the single source of truth for test totals quoted in
  README/CHANGELOG (never hand-copy a number into docs).

Exit code: 0 iff every selected suite passes.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

SUITES = ("harness", "generators", "scoring", "golden", "backends")


def suite_env():
    """Environment for an isolated suite subprocess (SPEC: stdlib only).

    PYTHONPATH is repo root + shared/ ONLY. The generators/ directory
    must NOT be appended: tests import the ``generators`` package
    (``from generators.task_dsl import ...``) while generator modules
    also support bare imports (``from task_dsl import ...``); putting
    both the package parent and the package itself on sys.path loads
    two distinct module objects (e.g. two TaskDSL classes) and breaks
    isinstance checks in generators/instance_factory.py.
    """
    env = dict(os.environ)
    extra = [ROOT, os.path.join(ROOT, "shared")]
    prev = env.get("PYTHONPATH", "")
    parts = extra + ([prev] if prev else [])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def run_suite(name):
    """Run one test directory in isolation. Returns (ok, summary_line, output)."""
    target = os.path.join(HERE, name)
    if not os.path.isdir(target):
        return False, "%-10s MISSING DIR" % name, ""
    # No -t flag: with -t, unittest requires the start dir to be an
    # importable package (tests/ has no __init__.py); without it the
    # top-level defaults to the start dir and absolute imports
    # resolve via PYTHONPATH above.
    cmd = [sys.executable, "-m", "unittest", "discover",
           "-s", target]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=suite_env(),
                              capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return False, "%-10s TIMEOUT (>600s)" % name, ""
    out = (proc.stderr or "") + (proc.stdout or "")
    last = " ".join(out.strip().splitlines()[-3:]) if out.strip() else "(no output)"
    ok = proc.returncode == 0
    # unittest prints "OK" to stderr on success; surface the tail.
    status = "PASS" if ok else "FAIL"
    return ok, "%-10s %s  [exit=%d] %s" % (name, status, proc.returncode,
                                          last[:220]), out


def count_suite(name):
    """Count test cases in one directory without running them.

    Runs in an isolated subprocess with the same PYTHONPATH as
    run_suite(), so package imports resolve identically (in-process
    counting would undercount when `generators` is not importable).
    """
    target = os.path.join(HERE, name)
    cmd = [sys.executable, "-c",
           "import unittest; print(unittest.TestLoader()"
           ".discover(%r).countTestCases())" % target]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=suite_env(),
                              capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return -1
    if proc.returncode != 0:
        return -1
    try:
        return int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return -1


def main(argv=None):
    argv = list(argv or [])
    if "--count" in argv:
        total = 0
        for name in SUITES:
            n = count_suite(name)
            total += n
            print("%-10s %d" % (name, n))
        print("%-10s %d" % ("total", total))
        return 0
    only = None
    if "--suite" in argv:
        idx = argv.index("--suite")
        only = argv[idx + 1] if idx + 1 < len(argv) else None
        if only not in SUITES:
            print("unknown suite %r (choose from %s)" % (only, ", ".join(SUITES)))
            return 2
    names = [only] if only else list(SUITES)
    print("EMO-X unified test run (isolated per-directory subprocesses)")
    print("root: %s" % ROOT)
    results = []
    for name in names:
        ok, line, out = run_suite(name)
        results.append((name, ok, line, out))
        print(line)
        if not ok and out.strip():
            # CI diagnosis (P0): the summary tail hides the traceback.
            # Print the head (first failure/error in full) so the log
            # shows the cause, not just "FAILED (errors=2)".
            print("----- %s first 80 lines (failure detail) -----" % name)
            for ln in out.strip().splitlines()[:80]:
                print(ln)
            print("----- end %s detail -----" % name)
    print("-" * 70)
    print("%-10s %-4s  detail" % ("suite", "pass"))
    for name, ok, _, _ in results:
        print("%-10s %-4s" % (name, "YES" if ok else "NO"))
    print("-" * 70)
    failed = [n for n, ok, _, _ in results if not ok]
    if failed:
        print("RESULT: FAIL (%s)" % ", ".join(failed))
        return 1
    print("RESULT: PASS (all %d suites green)" % len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
