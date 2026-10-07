"""Generalization + novelty: default arithmetic (C47), gap/retention."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


class TestGeneralization(unittest.TestCase):
    def test_default_is_arithmetic_c47(self):
        self.assertAlmostEqual(scoring.generalization_score([1.0, 0.5]), 0.75)
        self.assertAlmostEqual(scoring.generalization_score([1.0, 0.5], mode="arithmetic"), 0.75)

    def test_harmonic_auxiliary(self):
        # 2 / (1/1 + 1/0.5) = 2/3
        self.assertAlmostEqual(scoring.generalization_score([1.0, 0.5], mode="harmonic"), 2 / 3)
        self.assertAlmostEqual(scoring.generalization_h([1.0, 0.5]), 2 / 3)

    def test_harmonic_penalizes_weak_novel(self):
        arith = scoring.generalization_score([1.0, 0.1])
        harm = scoring.generalization_h([1.0, 0.1])
        self.assertLess(harm, arith)

    def test_unobserved_excluded(self):
        self.assertAlmostEqual(scoring.generalization_score([1.0, None]), 1.0)
        self.assertIsNone(scoring.generalization_score([None, None]))
        self.assertIsNone(scoring.generalization_h([None]))


class TestNovelty(unittest.TestCase):
    def test_gap(self):
        self.assertAlmostEqual(scoring.novelty_gap(0.96, 0.91), 0.05)
        self.assertIsNone(scoring.novelty_gap(None, 0.5))

    def test_gap_benchmark_mean(self):
        self.assertAlmostEqual(scoring.novelty_gap_benchmark([(0.9, 0.8), (0.6, 0.6)]), 0.05)
        self.assertIsNone(scoring.novelty_gap_benchmark([]))

    def test_retention_per_task_b14(self):
        self.assertAlmostEqual(scoring.novelty_retention(0.8, 0.6), 0.75)
        self.assertAlmostEqual(scoring.novelty_retention(0.5, 0.9), 1.0)

    def test_retention_zero_canonical_is_na(self):
        self.assertIsNone(scoring.novelty_retention(0.0, 0.5))

    def test_retention_benchmark_ratio_of_sums_c48(self):
        # (0.6+0.4)/(0.8+0.4) = 1.0/1.2, NOT mean(0.75, 1.0)
        self.assertAlmostEqual(
            scoring.novelty_retention_benchmark([(0.8, 0.6), (0.4, 0.4)]), 1.0 / 1.2
        )
        self.assertIsNone(scoring.novelty_retention_benchmark([]))


if __name__ == "__main__":
    unittest.main()
