"""Benchmark health: B48-B53 / C69-C72 + judge reliability B52."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


class TestHealth(unittest.TestCase):
    def test_flakiness(self):
        self.assertAlmostEqual(scoring.flakiness(0.5), 1.0)
        self.assertAlmostEqual(scoring.flakiness(1.0), 0.0)

    def test_saturation(self):
        self.assertAlmostEqual(scoring.saturation_penalty(0.95), 0.0)
        self.assertAlmostEqual(scoring.saturation_penalty(1.0), 1.0)
        self.assertAlmostEqual(scoring.saturation_penalty(0.975), 0.5)
        self.assertIsNone(scoring.saturation_penalty(None))

    def test_discrimination_needs_5_models(self):
        pop = {"m%d" % i: {"T": 0.5 + 0.05 * i, "U": 0.4 + 0.05 * i} for i in range(5)}
        d = scoring.discrimination(pop, "T")
        self.assertIsNotNone(d)
        self.assertGreaterEqual(d, 0.0)
        small = {"m1": {"T": 0.5, "U": 0.4}, "m2": {"T": 0.6, "U": 0.5}}
        self.assertIsNone(scoring.discrimination(small, "T"))  # C70
        const = {"m%d" % i: {"T": 0.5, "U": 0.4} for i in range(5)}
        self.assertIsNone(scoring.discrimination(const, "T"))  # constant

    def test_validity(self):
        self.assertAlmostEqual(scoring.harness_validity(1, 100), 0.99)
        self.assertIsNone(scoring.harness_validity(0, 0))

    def test_judge_reliability(self):
        f1 = scoring.judge_reliability_macro_f1(["a", "b", "a"], ["a", "b", "b"], ["a", "b"])
        self.assertAlmostEqual(f1, (2 / 3 + 2 / 3) / 2, places=5)
        ba = scoring.judge_reliability_balanced_accuracy([1, 1, 0, 0], [1, 0, 1, 0])
        self.assertAlmostEqual(ba, 0.5)
        self.assertEqual(scoring.judge_confidence_mark(0.95), "OK")
        self.assertEqual(scoring.judge_confidence_mark(0.89), "LOW-CONFIDENCE")
        self.assertEqual(scoring.judge_confidence_mark(None), "LOW-CONFIDENCE")

    def test_task_health_na_exclusion(self):
        h = scoring.task_health([0.99, 0.8, 0.9, 1.0, None])
        self.assertAlmostEqual(h, (0.99 * 0.8 * 0.9 * 1.0) ** (1 / 4))
        self.assertIsNone(scoring.task_health([]))
        self.assertIsNone(scoring.task_health([None]))

    def test_benchmark_health(self):
        self.assertAlmostEqual(scoring.benchmark_health([0.8, 0.6, None]), 0.7)
        self.assertIsNone(scoring.benchmark_health([]))


if __name__ == "__main__":
    unittest.main()
