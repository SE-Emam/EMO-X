"""Canonical robustness signals: B40-B42 / C58-C59 (review P0-4)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


class TestRobustnessSignals(unittest.TestCase):
    def test_perfect_run(self):
        sig = scoring.robustness_from_drift(4, 4, 3, 3, 3)
        self.assertAlmostEqual(sig["state_awareness"], 1.0)
        self.assertAlmostEqual(sig["state_drift_error"], 0.0)
        self.assertAlmostEqual(sig["replanning_rate"], 1.0)
        self.assertAlmostEqual(sig["correct_replanning"], 1.0)
        self.assertAlmostEqual(sig["stale_plan_rate"], 0.0)
        self.assertAlmostEqual(sig["robustness"], 1.0)

    def test_partial_run_composite(self):
        sig = scoring.robustness_from_drift(2, 4, 2, 1, 4)
        self.assertAlmostEqual(sig["state_awareness"], 0.5)
        self.assertAlmostEqual(sig["stale_plan_rate"], 0.75)
        # composite = geomean(0.5, 0.25, 1-0.75)
        expect = (0.5 * 0.25 * 0.25) ** (1.0 / 3)
        self.assertAlmostEqual(sig["robustness"], expect)

    def test_empty_denominators_are_na(self):
        sig = scoring.robustness_from_drift(0, 0, 0, 0, 0)
        for key in ("state_awareness", "state_drift_error",
                    "replanning_rate", "correct_replanning",
                    "stale_plan_rate", "robustness"):
            self.assertIsNone(sig[key])


if __name__ == "__main__":
    unittest.main()
