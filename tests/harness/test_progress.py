"""Tests for live progress reporting (bar + title + MCP events).

Progress is ephemeral UI: enabling it must never change scored results
(events.jsonl byte-identical with progress on or off).
"""

import hashlib
import io
import os
import shutil
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from progress import ProgressReporter, NullProgress  # noqa: E402
from runner import run_suite, stub_chat_factory  # noqa: E402


def _hash_events(rundir):
    with open(os.path.join(rundir, "events.jsonl"), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class ProgressRenderTests(unittest.TestCase):
    def test_bar_zero_full(self):
        p = ProgressReporter(enabled=False)
        p.start_run(total_suites=1)
        p.start_suite("code25", total_attempts=4)
        self.assertIn("0%", p.render())
        self.assertIn("~--:--", p.render())  # ETA unknown before data
        for i in range(4):
            p.start_attempt("T%d" % i)
            p.finish_attempt("PASS" if i % 2 == 0 else "FAIL")
        self.assertIn("100%", p.render())
        self.assertIn("T3", p.render())  # current step title shown
        self.assertIn("2", p.render())  # tallies present

    def test_null_progress_noop(self):
        n = NullProgress()
        n.start_run(7)
        n.start_suite("x", total_attempts=9)
        n.start_attempt("t")
        n.finish_attempt("PASS")
        n.finish_suite()
        n.finish_run()
        self.assertEqual(n.snapshot(), {})

    def test_snapshot_shape(self):
        events = []
        p = ProgressReporter(enabled=False, on_event=events.append)
        p.start_run(total_suites=2)
        p.start_suite("code25", suite_idx=1, total_attempts=2)
        p.start_attempt("T1")
        p.finish_attempt("PASS")
        snap = events[-1]
        for key in ("suite", "suite_idx", "total_suites", "done",
                    "total", "title", "passed", "failed",
                    "elapsed_s", "eta_s"):
            self.assertIn(key, snap)
        self.assertEqual(snap["done"], 1)
        self.assertEqual(snap["passed"], 1)
        self.assertEqual(snap["title"], "T1")

    def test_monotonic_done(self):
        seen = []
        p = ProgressReporter(enabled=False,
                             on_event=lambda s: seen.append(s["done"]))
        p.start_run()
        p.start_suite("s", total_attempts=3)
        for i in range(3):
            p.start_attempt("t%d" % i)
            p.finish_attempt("FAIL")
        dones = [d for d in seen if isinstance(d, int)]
        self.assertEqual(sorted(dones), dones)
        self.assertEqual(dones[-1], 3)


class ProgressNeutralityTests(unittest.TestCase):
    def test_bundles_identical_with_and_without_progress(self):
        roots = []
        hashes = []
        try:
            for i in range(2):
                root = "/tmp/emox_progress_test_%d" % i
                shutil.rmtree(root, ignore_errors=True)
                roots.append(root)
                stream = io.StringIO() if i == 0 else None
                prog = ProgressReporter(
                    stream=stream, enabled=(i == 0))
                rundir, _ = run_suite(
                    "dynamic-code", stub_chat_factory("progress-test"),
                    "m", "stub", seed=1, instances=1, trials=1,
                    fault_rate=0.0,
                    out_root=os.path.join(root, "raw"),
                    families=["DC1"], progress=prog,
                    run_id="RUN-PROGRESS-TEST")
                hashes.append(_hash_events(rundir))
                if i == 0:
                    # The bar actually drew something.
                    self.assertIn("DC1", stream.getvalue())
            self.assertEqual(hashes[0], hashes[1])
        finally:
            for root in roots:
                shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
