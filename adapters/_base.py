"""Shared episode plumbing for CLI-agent adapters (roadmap 2.1).

Single home for the logic that was byte-identical across adapters:
git-diff evidence (`final_diff`), timeout decoding, and the timeout
trace envelope. Adapter-specific parts (probe parsing, CLI argv,
prompts, stop text) stay in each adapter — they encode genuinely
different harnesses, and merging them would invent false sameness.

Stdlib only. Importable standalone (`python adapters/x.py`) and via
adapter_runner: bare `from _base import ...` resolves in both modes
(adapters/ is sys.path[0] standalone, and on sys.path under runner).
"""

import subprocess


def final_diff(task_dir, trunc_diff=8000):
    """Best-effort (diff, files, error) triple from `git diff`."""
    try:
        p = subprocess.run(
            ["git", "diff"], cwd=task_dir, capture_output=True, text=True, timeout=60
        )
        diff = (p.stdout or "")[:trunc_diff]
    except Exception as e:  # noqa: BLE001 - diff is best-effort evidence
        return "", [], "git diff failed: %s" % e
    try:
        q = subprocess.run(
            ["git", "diff", "--name-only"], cwd=task_dir, capture_output=True, text=True, timeout=60
        )
        files = [ln for ln in (q.stdout or "").splitlines() if ln.strip()]
    except Exception:  # noqa: BLE001 - files list is auxiliary
        files = []
    return diff, files, None


def decode_bytes(value):
    """Decode subprocess byte streams; pass text through."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value or ""


def timeout_trace(
    adapter_name,
    model_id,
    task_dir,
    steps,
    err,
    timeout_s,
    harness,
    comparability,
    diff="",
    files=(),
):
    """Trace envelope for wall-clock exhaustion (stopped_cleanly=false)."""
    steps = list(steps)
    steps.append(
        {
            "tool": "timeout",
            "args": {"timeout_s": timeout_s},
            "result": (err[-500:] or "wall-clock budget exhausted"),
        }
    )
    for i, s in enumerate(steps, 1):
        s["index"] = i
    return {
        "adapter": adapter_name,
        "model_id": model_id,
        "task_dir": task_dir,
        "harness": harness,
        "steps": steps,
        "final_diff": diff,
        "diff_files": list(files),
        "stopped_cleanly": False,
        "timed_out": True,
        "exit_code": None,
        "stderr_tail": err[-500:],
        "comparability": comparability,
    }
