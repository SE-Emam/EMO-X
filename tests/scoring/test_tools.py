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


def _agent_attempt(**over):
    rec = {"task_family_id": "AG", "instance_id": "AG-canonical-00001",
           "variant_class": "canonical", "trial_id": 1,
           "primary_status": "PASS", "score": 1.0,
           "A": {"A1_recon_before_edit": True, "A2_ran_tests": True,
                 "A3_intended_file": True, "A4_no_forbidden": True,
                 "A5_no_hallucinated_paths": True,
                 "A8_verify_after_edit": True,
                 "A10_config_untouched": True},
           "tool_calls": 8, "failed_calls": 1}
    rec.update(over)
    return rec


class TestAgentComponents(unittest.TestCase):
    def test_components_from_observables(self):
        comp = scoring.tool_components_from_agent_attempt(_agent_attempt())
        self.assertAlmostEqual(comp["precision"], 7 / 8)
        self.assertAlmostEqual(comp["recall"], 1.0)
        self.assertAlmostEqual(comp["sequence_validity"], 1.0)
        self.assertAlmostEqual(comp["side_effect_safety"], 1.0)
        self.assertIsNone(comp["argument_accuracy"])
        self.assertIsNone(comp["action_discipline"])

    def test_discipline_mean_over_attempts(self):
        good = _agent_attempt()
        sloppy = _agent_attempt(
            trial_id=2,
            A=dict(good["A"], A2_ran_tests=False, A4_no_forbidden=False),
            tool_calls=10, failed_calls=5)
        value = scoring.tool_discipline_from_attempts([good, sloppy])
        self.assertIsNotNone(value)
        self.assertLess(value, scoring.tool_discipline(
            scoring.tool_components_from_agent_attempt(good).values()))

    def test_no_agent_data_is_na(self):
        self.assertIsNone(scoring.tool_discipline_from_attempts(
            [{"task_family_id": "H3"}]))
        self.assertIsNone(scoring.tool_discipline_from_attempts([]))


if __name__ == "__main__":
    unittest.main()
