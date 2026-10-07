"""Golden edge-case table: every row of DEN C82 verified end-to-end.

Each row: situation -> numerator/denominator -> expected result.
D=0 => NA (None), never 0, unless the row explicitly says otherwise.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
JUDGES = os.path.normpath(os.path.join(HERE, "..", "..", "judges"))
for p in (SHARED, JUDGES):
    if p not in sys.path:
        sys.path.insert(0, p)

import scoring
import trajectory


def ev(task, inst, status, score, **kw):
    d = {
        "run_id": "R",
        "model_id": "M",
        "task_family_id": task,
        "instance_id": inst,
        "variant_class": "canonical",
        "trial_id": 1,
        "primary_status": status,
        "score": score,
    }
    d.update(kw)
    return d


class TestGoldenEdgeTableC82(unittest.TestCase):
    def test_all_pass_is_one(self):
        events = [ev("T", "i1", "PASS", 1.0), ev("T", "i2", "PASS", 1.0)]
        self.assertAlmostEqual(scoring.pass_rate(events), 1.0)

    def test_mixed_pass_fail_is_ratio(self):
        events = [ev("T", "i1", "PASS", 1.0), ev("T", "i2", "FAIL", 0.0)]
        self.assertAlmostEqual(scoring.pass_rate(events), 0.5)

    def test_all_void_is_na(self):
        events = [ev("T", "i1", "VOID", 0.0), ev("T", "i2", "VOID", 0.0)]
        self.assertIsNone(scoring.pass_rate(events))
        self.assertIsNone(scoring.aggregate_events(events)["suite_score"])
        self.assertAlmostEqual(scoring.coverage(events), 0.0)

    def test_all_error_is_na(self):
        events = [ev("T", "i1", "ERROR", 0.0)]
        self.assertIsNone(scoring.pass_rate(events))
        self.assertIsNone(scoring.aggregate_events(events)["suite_score"])

    def test_never_attempted_is_na(self):
        self.assertIsNone(scoring.aggregate_families_to_suite([]))
        self.assertIsNone(scoring.pass_rate([]))

    def test_no_tool_required_is_na(self):
        self.assertIsNone(scoring.tool_precision(0, 0))
        self.assertIsNone(scoring.tool_recall(0, 0))
        self.assertIsNone(scoring.tool_discipline([None, None]))

    def test_tool_required_but_unused_is_zero_recall(self):
        self.assertAlmostEqual(scoring.tool_recall(0, 2), 0.0)

    def test_zero_solves_cost_na(self):
        events = [ev("T", "i1", "FAIL", 0.0, tokens=10, cost=0.3)]
        self.assertIsNone(scoring.efficiency_per_solve(events, "tokens"))
        self.assertIsNone(scoring.cost_per_solve(events))

    def test_zero_abstentions_na(self):
        m = scoring.abstention_metrics(4, 4, 0, 0)
        self.assertIsNone(m["correct_abstention_rate"])

    def test_no_drift_is_na(self):
        self.assertIsNone(scoring.state_awareness(0, 0))

    def test_no_recovery_fault_is_na(self):
        self.assertIsNone(scoring.recovery_rate([]))

    def test_missing_human_time_excluded(self):
        out = scoring.time_horizon_fit([{"human_minutes": None, "n_attempts": 3, "n_success": 1}])
        self.assertFalse(out["valid"])
        self.assertIsNone(scoring.human_minutes_solved([{"human_minutes": None, "score": 1.0}]))

    def test_missing_confidence_excluded(self):
        cases = [{"confidence": None, "outcome": 1}]
        self.assertIsNone(scoring.brier_score(cases))
        self.assertIsNone(scoring.expected_calibration_error(cases))
        self.assertIsNone(scoring.calibration_score(cases))

    def test_infra_timeout_is_void(self):
        # infrastructure-caused timeout -> VOID -> excluded, NA alone (C7)
        events = [ev("T", "i1", "VOID", 0.0)]
        self.assertIsNone(scoring.pass_rate(events))

    def test_model_timeout_is_zero(self):
        # model-caused TIMEOUT is scored 0, FAIL-equivalent (C7)
        events = [ev("T", "i1", "TIMEOUT", 0.0), ev("T", "i2", "PASS", 1.0)]
        self.assertAlmostEqual(scoring.pass_rate(events), 0.5)
        prim = trajectory.classify_primary_failure(["TIMEOUT", "WRONG_RESULT"])
        self.assertEqual(prim, "TIMEOUT")  # precedence C25

    def test_invalid_scored_zero(self):
        events = [ev("T", "i1", "INVALID", 0.0)]
        self.assertAlmostEqual(scoring.pass_rate(events), 0.0)


if __name__ == "__main__":
    unittest.main()
