"""Trajectory/state/clean-stop/verification + judge oracles."""

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
import deterministic
import execution
import trajectory
import llm_judge


class TestStopVerifyDrift(unittest.TestCase):
    def test_clean_stop(self):
        self.assertAlmostEqual(scoring.clean_stop_rate(9, 10), 0.9)
        self.assertIsNone(scoring.clean_stop_rate(0, 0))

    def test_verification(self):
        self.assertAlmostEqual(scoring.verification_rate(7, 10), 0.7)
        self.assertIsNone(scoring.verification_rate(0, 0))

    def test_state_awareness_na_without_injection(self):
        self.assertIsNone(scoring.state_awareness(0, 0))
        self.assertAlmostEqual(scoring.state_awareness(3, 4), 0.75)

    def test_stale_replan(self):
        self.assertAlmostEqual(scoring.stale_plan_rate(2, 4), 0.5)
        self.assertAlmostEqual(scoring.correct_replanning_rate(3, 4), 0.75)
        self.assertIsNone(scoring.stale_plan_rate(0, 0))
        self.assertIsNone(scoring.correct_replanning_rate(0, 0))

    def test_failure_fingerprint_sums(self):
        events = [
            {"primary_status": "FAIL", "primary_failure": "WRONG_TOOL"},
            {"primary_status": "FAIL", "primary_failure": "WRONG_RESULT"},
            {"primary_status": "PASS", "primary_failure": None},
            {"primary_status": "VOID", "primary_failure": None},
        ]
        fp = scoring.failure_fingerprint(events)
        self.assertAlmostEqual(fp["WRONG_TOOL"] + fp["WRONG_RESULT"], 2 / 3)
        self.assertEqual(scoring.failure_fingerprint([]), {})


class TestTrajectoryJudge(unittest.TestCase):
    def test_precedence_c25(self):
        self.assertEqual(
            trajectory.classify_primary_failure(["WRONG_RESULT", "WRONG_TOOL"]), "WRONG_TOOL"
        )
        self.assertEqual(trajectory.classify_primary_failure(["STALE_PLAN"]), "STALE_PLAN")
        self.assertIsNone(trajectory.classify_primary_failure([]))

    def test_exactly_one_primary(self):
        rec = trajectory.validate_failure_record("WRONG_TOOL", ["WRONG_ARGUMENT"])
        self.assertEqual(rec["primary_failure"], "WRONG_TOOL")
        with self.assertRaises(ValueError):
            trajectory.validate_failure_record("WRONG_TOOL", ["WRONG_TOOL"])
        with self.assertRaises(ValueError):
            trajectory.validate_failure_record(None, ["WRONG_TOOL"])

    def test_deterministic_oracles(self):
        self.assertEqual(deterministic.exact_match("a", "a")["verdict"], "PASS")
        self.assertEqual(deterministic.exact_match("a", "b")["verdict"], "FAIL")
        self.assertEqual(deterministic.numeric_match("1.0", 1.0, 0.01)["verdict"], "PASS")
        self.assertEqual(deterministic.set_match([1, 2], [2, 1])["verdict"], "PASS")

    def test_execution_oracles(self):
        self.assertEqual(execution.tests_verdict(5, 5)["verdict"], "PASS")
        self.assertEqual(execution.tests_verdict(3, 5)["verdict"], "PARTIAL")
        self.assertEqual(execution.tests_verdict(0, 0)["verdict"], "VOID")
        self.assertEqual(execution.exit_code_verdict(0)["verdict"], "PASS")

    def test_llm_judge_reliability_hooks(self):
        rep = llm_judge.reliability_report(
            ["PASS", "FAIL", "PASS"], ["PASS", "FAIL", "FAIL"], kind="binary"
        )
        self.assertIn("reliability", rep)
        self.assertIn(rep["mark"], ("OK", "LOW-CONFIDENCE"))
        bad = llm_judge.reliability_report([1, 1, 1, 1], [1, 0, 1, 0], kind="binary")
        self.assertEqual(bad["mark"], "LOW-CONFIDENCE")
        self.assertFalse(bad["usable_as_headline"])
        self.assertEqual(llm_judge.parse_judge_verdict("pass")["verdict"], "PASS")
        self.assertEqual(llm_judge.parse_judge_verdict("???")["verdict"], "INVALID")


if __name__ == "__main__":
    unittest.main()
