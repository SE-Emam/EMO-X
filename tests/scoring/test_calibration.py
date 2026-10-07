"""Calibration + abstention: B32-B35 / C50-C53."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


class TestCalibration(unittest.TestCase):
    def test_brier_golden(self):
        cases = [{"confidence": 0.8, "outcome": 1}, {"confidence": 0.2, "outcome": 0}]
        self.assertAlmostEqual(scoring.brier_score(cases), 0.04)

    def test_brier_excludes_missing_confidence_c50(self):
        cases = [{"confidence": 0.8, "outcome": 1}, {"confidence": None, "outcome": 0}]
        self.assertAlmostEqual(scoring.brier_score(cases), 0.04)
        self.assertIsNone(scoring.brier_score([]))

    def test_ece_golden(self):
        cases = [{"confidence": 0.9, "outcome": 1}, {"confidence": 0.1, "outcome": 0}]
        self.assertAlmostEqual(scoring.expected_calibration_error(cases), 0.1)

    def test_calibration_score(self):
        cases = [{"confidence": 0.9, "outcome": 1}, {"confidence": 0.1, "outcome": 0}]
        b = scoring.brier_score(cases)
        e = scoring.expected_calibration_error(cases)
        self.assertAlmostEqual(scoring.calibration_score(cases), 1 - (b + e) / 2)
        self.assertIsNone(scoring.calibration_score([]))

    def test_abstention(self):
        m = scoring.abstention_metrics(8, 6, 2, 2)
        self.assertAlmostEqual(m["answer_accuracy"], 6 / 8)
        self.assertAlmostEqual(m["correct_abstention_rate"], 1.0)
        self.assertAlmostEqual(m["selective_risk"], 2 / 8)
        self.assertAlmostEqual(m["decision_accuracy"], 8 / 10)
        self.assertAlmostEqual(m["answer_coverage"], 0.8)

    def test_zero_abstentions_is_na(self):
        m = scoring.abstention_metrics(5, 5, 0, 0)
        self.assertIsNone(m["correct_abstention_rate"])
        self.assertAlmostEqual(m["decision_accuracy"], 1.0)

    def test_zero_answered_is_na(self):
        m = scoring.abstention_metrics(0, 0, 3, 2)
        self.assertIsNone(m["answer_accuracy"])
        self.assertIsNone(m["selective_risk"])


if __name__ == "__main__":
    unittest.main()
