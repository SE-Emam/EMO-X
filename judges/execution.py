"""Tier 2 execution/compiler oracle interface. SPEC P6 hierarchy.

Pure mapping from recorded execution facts (exit codes, test tallies)
to scored outcomes. No subprocesses run here; execution itself lives in
shared/sandbox.py (X-1 ownership).
"""


def tests_verdict(passed, total):
    """Map a test tally to a verdict. All pass => PASS, some => PARTIAL."""
    if total is None or total <= 0:
        return {"verdict": "VOID", "score": None, "note": "no tests to judge"}
    if passed >= total:
        return {"verdict": "PASS", "score": 1.0}
    if passed <= 0:
        return {"verdict": "FAIL", "score": 0.0}
    return {"verdict": "PARTIAL", "score": passed / total}


def exit_code_verdict(exit_code, tests=None):
    """Map a process exit code (+ optional test tally) to a verdict."""
    if exit_code is None:
        return {
            "verdict": "ERROR",
            "score": None,
            "note": "missing exit code is infra-unknown, not FAIL",
        }
    if tests is not None:
        passed, total = tests
        return tests_verdict(passed, total)
    ok = exit_code == 0
    return {"verdict": "PASS" if ok else "FAIL", "score": 1.0 if ok else 0.0}


def compile_verdict(compiled, test_verdict=None):
    """Two-gate verdict: compile must succeed before test credit counts."""
    if not compiled:
        return {"verdict": "FAIL", "score": 0.0}
    if test_verdict is None:
        return {"verdict": "PASS", "score": 1.0}
    return test_verdict
