"""Long horizon, human minutes, time horizon, scaffold gain: B44-B47."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


class TestHorizon(unittest.TestCase):
    def test_step_survival(self):
        self.assertAlmostEqual(scoring.step_survival(7, 10), 0.7)
        self.assertIsNone(scoring.step_survival(0, 0))

    def test_survival_at_k(self):
        self.assertAlmostEqual(scoring.survival_at_k(8, 10), 0.8)
        self.assertIsNone(scoring.survival_at_k(0, 0))

    def test_human_minutes(self):
        tasks = [
            {"human_minutes": 10, "score": 1.0},
            {"human_minutes": 20, "score": 0.5},
            {"human_minutes": None, "score": 1.0},
        ]
        self.assertAlmostEqual(scoring.human_minutes_solved(tasks), 20.0)
        strict = [
            {"human_minutes": 10, "strict_pass": True},
            {"human_minutes": 20, "strict_pass": False},
        ]
        self.assertAlmostEqual(scoring.human_minutes_strict(strict), 10.0)
        self.assertAlmostEqual(scoring.human_minutes_rate(tasks), 20.0 / 30.0)
        self.assertIsNone(scoring.human_minutes_solved([]))

    def test_time_horizon_valid(self):
        # easy tasks pass, hard tasks fail -> decreasing curve, valid
        tasks = [
            {"human_minutes": 1, "n_attempts": 10, "n_success": 9},
            {"human_minutes": 2, "n_attempts": 10, "n_success": 8},
            {"human_minutes": 10, "n_attempts": 10, "n_success": 3},
            {"human_minutes": 30, "n_attempts": 10, "n_success": 1},
        ]
        out = scoring.time_horizon_fit(tasks)
        self.assertTrue(out["valid"])
        self.assertTrue(out["converged"])
        self.assertLess(out["beta"], 0)
        self.assertGreater(out["h50"], 0)
        # decreasing curve: higher reliability => shorter (easier) horizon
        self.assertLess(out["h80"], out["h50"])

    def test_time_horizon_beta_nonneg_invalid(self):
        # harder tasks succeed MORE -> beta >= 0 -> invalid (B46)
        tasks = [
            {"human_minutes": 1, "n_attempts": 10, "n_success": 1},
            {"human_minutes": 2, "n_attempts": 10, "n_success": 3},
            {"human_minutes": 10, "n_attempts": 10, "n_success": 8},
            {"human_minutes": 30, "n_attempts": 10, "n_success": 9},
        ]
        out = scoring.time_horizon_fit(tasks)
        self.assertFalse(out["valid"])
        self.assertIsNone(out["h50"])

    def test_time_horizon_excludes_missing(self):
        tasks = [
            {"human_minutes": None, "n_attempts": 5, "n_success": 3},
            {"human_minutes": 5, "n_attempts": 0, "n_success": 0},
        ]
        out = scoring.time_horizon_fit(tasks)
        self.assertFalse(out["valid"])  # C64: nothing eligible
        self.assertFalse(out["converged"])

    def test_non_convergent_fit_is_invalid(self):
        # starving the solver of iterations must fail closed, never
        # read as a valid fit (auditor P1-15).
        tasks = [
            {"human_minutes": 1, "n_attempts": 10, "n_success": 9},
            {"human_minutes": 2, "n_attempts": 10, "n_success": 8},
            {"human_minutes": 10, "n_attempts": 10, "n_success": 3},
            {"human_minutes": 30, "n_attempts": 10, "n_success": 1},
        ]
        out = scoring.time_horizon_fit(tasks, max_iter=1)
        self.assertFalse(out["converged"])
        self.assertFalse(out["valid"])
        self.assertEqual(out["reason"], "non-convergent")

    def test_scaffold_gain(self):
        g = scoring.scaffold_gain(0.5, 0.7)
        self.assertAlmostEqual(g["absolute"], 0.2)
        self.assertAlmostEqual(g["relative"], 0.4)
        self.assertIsNone(scoring.scaffold_gain(None, 0.7)["absolute"])


if __name__ == "__main__":
    unittest.main()
