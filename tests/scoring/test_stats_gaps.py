"""Wilson intervals, MDE, cost/Pareto (roadmap: EvalSig + HAL gaps)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


class WilsonTests(unittest.TestCase):
    def test_stays_in_unit_interval(self):
        for k, n in ((0, 1), (1, 1), (0, 5), (5, 5), (24, 25)):
            w = scoring.wilson_interval(k, n)
            self.assertGreaterEqual(w["low"], 0.0)
            self.assertLessEqual(w["high"], 1.0)
            self.assertLessEqual(w["low"], w["high"])

    def test_wald_would_escape_but_wilson_does_not(self):
        # 24/25: Wald upper = p+1.96*se > 1; Wilson stays inside.
        import math

        p = 24 / 25
        wald_high = p + 1.96 * math.sqrt(p * (1 - p) / 25)
        self.assertGreater(wald_high, 1.0)
        self.assertLessEqual(scoring.wilson_interval(24, 25)["high"], 1.0)

    def test_empty_is_na(self):
        self.assertEqual(scoring.wilson_interval(0, 0), {"low": None, "high": None})


class MdeTests(unittest.TestCase):
    def test_scales_with_se(self):
        self.assertAlmostEqual(scoring.mde_paired(0.05), 2.8 * 0.05)
        self.assertIsNone(scoring.mde_paired(None))
        self.assertIsNone(scoring.mde_paired(float("nan")))


class CostParetoTests(unittest.TestCase):
    def test_usd_per_solve(self):
        self.assertAlmostEqual(
            scoring.usd_per_solve(1_000_000, 500_000, 1.0, 4.0, 10), (1.0 + 2.0) / 10
        )
        self.assertIsNone(scoring.usd_per_solve(1, 1, 1.0, 1.0, 0))
        with self.assertRaises(ValueError):
            scoring.usd_per_solve(1, 1, -1.0, 1.0, 1)

    def test_frontier_drops_dominated(self):
        pts = [
            {"label": "cheap-good", "cost": 1.0, "accuracy": 0.8},
            {"label": "pricey-same", "cost": 9.0, "accuracy": 0.8},
            {"label": "pricey-better", "cost": 9.0, "accuracy": 0.9},
            {"label": "broken", "cost": None, "accuracy": 0.5},
        ]
        front = scoring.pareto_frontier(pts)
        labels = [p["label"] for p in front]
        self.assertIn("cheap-good", labels)
        self.assertIn("pricey-better", labels)
        self.assertNotIn("pricey-same", labels)
        self.assertNotIn("broken", labels)
        self.assertEqual([p["cost"] for p in front], sorted(p["cost"] for p in front))


if __name__ == "__main__":
    unittest.main()
