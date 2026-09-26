"""Tool discipline: B15-B22 / C33-C41."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


class TestTools(unittest.TestCase):
    def test_precision_recall_f1(self):
        p = scoring.tool_precision(2, 4)
        r = scoring.tool_recall(2, 2)
        self.assertAlmostEqual(p, 0.5)
        self.assertAlmostEqual(r, 1.0)
        self.assertAlmostEqual(scoring.tool_f1(p, r), 2 * 0.5 / 1.5)

    def test_no_tool_required_is_na(self):
        self.assertIsNone(scoring.tool_precision(0, 0))
        self.assertIsNone(scoring.tool_recall(0, 0))
        self.assertIsNone(scoring.tool_f1(None, None))

    def test_required_but_unused_is_zero_recall(self):
        self.assertAlmostEqual(scoring.tool_recall(0, 3), 0.0)

    def test_f1_zero_sum(self):
        self.assertAlmostEqual(scoring.tool_f1(0.0, 0.0, True), 0.0)
        self.assertIsNone(scoring.tool_f1(0.0, 0.0, False))

    def test_argument_accuracy(self):
        self.assertAlmostEqual(scoring.argument_accuracy(3, 4), 0.75)
        self.assertIsNone(scoring.argument_accuracy(0, 0))

    def test_sequence_validity(self):
        self.assertAlmostEqual(scoring.sequence_validity(2, 3), 2 / 3)
        self.assertIsNone(scoring.sequence_validity(0, 0))

    def test_uar_and_discipline(self):
        self.assertAlmostEqual(scoring.unnecessary_action_rate(8, 13), 8 / 13)
        self.assertIsNone(scoring.unnecessary_action_rate(0, 0))
        self.assertAlmostEqual(scoring.action_discipline(8 / 13), 5 / 13)
        self.assertIsNone(scoring.action_discipline(None))

    def test_side_effect_safety(self):
        self.assertAlmostEqual(scoring.side_effect_safety(1, 4), 0.75)
        self.assertIsNone(scoring.side_effect_safety(0, 0))

    def test_tool_discipline_geomean_na_exclusion(self):
        td = scoring.tool_discipline([0.5, 1.0, None])
        self.assertAlmostEqual(td, (0.5 * 1.0) ** 0.5)
        self.assertIsNone(scoring.tool_discipline([]))
        self.assertIsNone(scoring.tool_discipline([None]))


if __name__ == "__main__":
    unittest.main()
