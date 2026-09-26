"""Tests for shared/invariants.py (stdlib unittest). Review P0-5.

JSON Schema (schemas.py) + Semantic Validator (invariants.py) = contract.
Every example in the review (PASS+0.40, FAIL+1.00, duplicates, missing
failure labels, bad trials, unknown variants) must raise loudly.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(os.path.dirname(HERE), "..", "shared")
SHARED = os.path.normpath(SHARED)
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import invariants


def good_attempt(**over):
    rec = {"run_id": "r1", "model_id": "m1", "task_family_id": "H3",
           "instance_id": "H3-00017", "variant_class": "structural",
           "trial_id": 1, "primary_status": "PASS", "score": 1.0,
           "eligible_for_task_score": True,
           "eligible_for_pass_rate": True,
           "eligible_for_efficiency": True,
           "eligible_for_calibration": False,
           "primary_failure": None, "secondary_failure_tags": []}
    rec.update(over)
    return rec


def failed_attempt(**over):
    rec = good_attempt(primary_status="FAIL", score=0.0,
                       primary_failure="WRONG_RESULT")
    rec.update(over)
    return rec


class AttemptSemanticsTests(unittest.TestCase):
    def test_valid_pass(self):
        self.assertTrue(invariants.validate_attempt_semantics(
            good_attempt()))

    def test_pass_with_partial_score_rejected(self):
        with self.assertRaises(ValueError):
            invariants.validate_attempt_semantics(
                good_attempt(score=0.40))

    def test_fail_with_full_score_rejected(self):
        with self.assertRaises(ValueError):
            invariants.validate_attempt_semantics(
                failed_attempt(score=1.00))

    def test_fail_without_failure_label_rejected(self):
        with self.assertRaises(ValueError):
            invariants.validate_attempt_semantics(
                failed_attempt(primary_failure=None))

    def test_pass_with_failure_label_rejected(self):
        with self.assertRaises(ValueError):
            invariants.validate_attempt_semantics(
                good_attempt(primary_failure="WRONG_RESULT"))

    def test_partial_requires_middle_score(self):
        self.assertTrue(invariants.validate_attempt_semantics(
            good_attempt(primary_status="PARTIAL", score=0.5,
                         primary_failure="PARTIAL_RESULT")))
        for bad in (0.0, 1.0):
            with self.assertRaises(ValueError):
                invariants.validate_attempt_semantics(
                    good_attempt(primary_status="PARTIAL", score=bad,
                                 primary_failure="PARTIAL_RESULT"))

    def test_bad_trial_id_rejected(self):
        for bad in (0, -1, "1", 1.5, True):
            with self.assertRaises(ValueError):
                invariants.validate_attempt_semantics(
                    good_attempt(trial_id=bad))


class RunSemanticsTests(unittest.TestCase):
    def test_duplicate_identity_rejected(self):
        with self.assertRaises(ValueError):
            invariants.validate_run_semantics(
                [good_attempt(), good_attempt()])

    def test_distinct_trials_pass(self):
        self.assertTrue(invariants.validate_run_semantics(
            [good_attempt(trial_id=1), good_attempt(trial_id=2)],
            expected_trials=2))

    def test_wrong_trial_count_rejected(self):
        with self.assertRaises(ValueError):
            invariants.validate_run_semantics(
                [good_attempt(trial_id=1)], expected_trials=3)

    def test_unknown_variant_rejected_with_manifest(self):
        manifest = {"task_families": {
            "H3": {"variant_classes": ["canonical", "structural"]}}}
        with self.assertRaises(ValueError):
            invariants.validate_run_semantics(
                [good_attempt(variant_class="novel")], manifest=manifest)
        self.assertTrue(invariants.validate_run_semantics(
            [good_attempt()], manifest=manifest))

    def test_report_gate_rejects_bad_raw(self):
        import report_v2
        with self.assertRaises(ValueError):
            report_v2.build_v2_report(
                [good_attempt(score=0.40)], model_id="m1")


if __name__ == "__main__":
    unittest.main()
