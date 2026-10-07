"""Guards for scoring tool functions + novelty zero-collapse (P1-05/P1-06).

- novelty_robustness: explicit zero-collapse — any 0.0 level yields 0.0
  (SPEC B13/B14, DEN C48/C49) instead of the eps-clamped near-zero.
- _finite: NaN/Inf inputs to tool_precision/recall/f1,
  argument_accuracy, sequence_validity raise ValueError (SPEC B15-B19,
  DEN C33-C38: fail closed on broken upstream ratios).
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring  # noqa: E402

NAN = float("nan")
INF = float("inf")
NINF = float("-inf")


class TestNoveltyZeroCollapse(unittest.TestCase):
    def test_novel_collapse_is_zero(self):
        self.assertEqual(scoring.novelty_robustness(1.0, 0.9, 0.0), 0.0)

    def test_perturbed_collapse_is_zero(self):
        self.assertEqual(scoring.novelty_robustness(1.0, 0.0, 0.9), 0.0)

    def test_canonical_collapse_is_zero(self):
        self.assertEqual(scoring.novelty_robustness(0.0, 0.9, 0.9), 0.0)

    def test_all_zero_is_zero(self):
        self.assertEqual(scoring.novelty_robustness(0.0, 0.0, 0.0), 0.0)

    def test_int_zero_collapses(self):
        self.assertEqual(scoring.novelty_robustness(1.0, 1.0, 0), 0.0)

    def test_nonzero_still_harmonic(self):
        # Golden cross-check: nonzero inputs keep the harmonic form
        # (existing goldens in test_golden_formulas use nonzero inputs).
        val = scoring.novelty_robustness(1.0, 0.90, 0.20)
        self.assertLess(val, 0.50)
        self.assertGreater(val, 0.0)
        hi = scoring.novelty_robustness(0.96, 0.92, 0.94)
        self.assertGreater(hi, 0.90)

    def test_na_and_negative_unchanged(self):
        self.assertIsNone(scoring.novelty_robustness(0.0, 0.9, None))
        self.assertIsNone(scoring.novelty_robustness(-0.1, 0.9, 0.9))


class TestFiniteGuards(unittest.TestCase):
    def test_precision_rejects_nonfinite(self):
        for bad in (NAN, INF, NINF):
            with self.assertRaises(ValueError):
                scoring.tool_precision(bad, 4)
            with self.assertRaises(ValueError):
                scoring.tool_precision(2, bad)
        self.assertAlmostEqual(scoring.tool_precision(2, 4), 0.5)
        self.assertIsNone(scoring.tool_precision(0, 0))

    def test_recall_rejects_nonfinite(self):
        for bad in (NAN, INF, NINF):
            with self.assertRaises(ValueError):
                scoring.tool_recall(bad, 2)
            with self.assertRaises(ValueError):
                scoring.tool_recall(0, bad)
        self.assertAlmostEqual(scoring.tool_recall(2, 2), 1.0)
        self.assertIsNone(scoring.tool_recall(0, 0))

    def test_f1_rejects_nonfinite(self):
        for bad in (NAN, INF, NINF):
            with self.assertRaises(ValueError):
                scoring.tool_f1(bad, 1.0)
            with self.assertRaises(ValueError):
                scoring.tool_f1(1.0, bad)
            with self.assertRaises(ValueError):
                scoring.tool_f1(bad, None)
        self.assertIsNone(scoring.tool_f1(None, None))
        self.assertIsNone(scoring.tool_f1(None, 1.0))
        self.assertAlmostEqual(scoring.tool_f1(0.5, 1.0), 2 * 0.5 / 1.5)

    def test_argument_accuracy_rejects_nonfinite(self):
        for bad in (NAN, INF, NINF):
            with self.assertRaises(ValueError):
                scoring.argument_accuracy(bad, 4)
            with self.assertRaises(ValueError):
                scoring.argument_accuracy(3, bad)
        self.assertAlmostEqual(scoring.argument_accuracy(3, 4), 0.75)
        self.assertIsNone(scoring.argument_accuracy(0, 0))

    def test_sequence_validity_rejects_nonfinite(self):
        for bad in (NAN, INF, NINF):
            with self.assertRaises(ValueError):
                scoring.sequence_validity(bad, 3)
            with self.assertRaises(ValueError):
                scoring.sequence_validity(2, bad)
        self.assertAlmostEqual(scoring.sequence_validity(2, 3), 2 / 3)
        self.assertIsNone(scoring.sequence_validity(0, 0))


if __name__ == "__main__":
    unittest.main()
