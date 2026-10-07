"""Report wiring: canonical tool/robustness signals (review P0-3/P0-4)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(os.path.dirname(HERE), "..", "shared")
SHARED = os.path.normpath(SHARED)
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import report_v2


def base(**over):
    rec = {
        "run_id": "r1",
        "model_id": "m1",
        "task_family_id": "H3",
        "instance_id": "H3-1",
        "variant_class": "canonical",
        "trial_id": 1,
        "primary_status": "PASS",
        "score": 1.0,
        "eligible_for_task_score": True,
        "eligible_for_pass_rate": True,
        "eligible_for_efficiency": True,
        "eligible_for_calibration": False,
        "primary_failure": None,
        "secondary_failure_tags": [],
    }
    rec.update(over)
    return rec


def drift_attempt(family, passed, idx):
    return base(
        task_family_id=family,
        instance_id="%s-%d" % (family, idx),
        primary_status="PASS" if passed else "FAIL",
        score=1.0 if passed else 0.0,
        primary_failure=None if passed else "STATE_DRIFT",
    )


def drift_response(family, idx, reply):
    return {
        "instance_id": "%s-%d" % (family, idx),
        "trial_id": 1,
        "reply": reply,
        "drift_injected": True,
    }


class ReportWiringTests(unittest.TestCase):
    def test_robustness_signals_from_episodes(self):
        attempts = [
            drift_attempt("RB1", True, 1),
            drift_attempt("RB1", False, 2),
            drift_attempt("RB2", True, 1),
            drift_attempt("RB2", False, 2),
        ]
        responses = [
            drift_response("RB1", 1, "fresh value seen"),
            drift_response("RB1", 2, "stale value kept"),
            drift_response("RB2", 1, "replan via source file"),
            drift_response("RB2", 2, "keep going, no change"),
        ]
        rep = report_v2.build_v2_report(attempts, responses, model_id="m")
        sig = rep["robustness_signals"]
        self.assertAlmostEqual(sig["state_awareness"], 0.5)
        self.assertAlmostEqual(sig["correct_replanning"], 0.5)
        self.assertAlmostEqual(sig["stale_plan_rate"], 0.5)
        self.assertAlmostEqual(sig["replanning_rate"], 0.5)
        self.assertIsNotNone(rep["capability_profile"]["robustness"])

    def test_tool_dimension_from_agent_attempt(self):
        attempt = base(
            task_family_id="AG",
            instance_id="AG-canonical-00001",
            A={
                "A1_recon_before_edit": True,
                "A2_ran_tests": True,
                "A3_intended_file": True,
                "A4_no_forbidden": True,
                "A5_no_hallucinated_paths": True,
                "A8_verify_after_edit": True,
                "A10_config_untouched": True,
            },
            tool_calls=8,
            failed_calls=1,
        )
        rep = report_v2.build_v2_report([attempt], [], model_id="m")
        self.assertIsNotNone(rep["capability_profile"]["tool_discipline"])
        self.assertAlmostEqual(rep["tool_components"]["precision"], 7 / 8)

    def test_no_signals_is_na_not_zero(self):
        rep = report_v2.build_v2_report([base()], [], model_id="m")
        self.assertIsNone(rep["capability_profile"]["tool_discipline"])
        self.assertIsNone(rep["capability_profile"]["robustness"])
        self.assertIsNone(rep["tool_components"])
        for value in rep["robustness_signals"].values():
            self.assertIsNone(value)


if __name__ == "__main__":
    unittest.main()
