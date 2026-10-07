"""ATIF export/validation + canary check + ASR matrix + pass^k."""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
for _p in (ROOT, SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scoring  # noqa: E402
import report_v2  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ATIF = _load("atif_under_test", os.path.join(SHARED, "atif.py"))
sys.path.insert(0, os.path.join(ROOT, "health"))
import contamination  # noqa: E402


class AtifTests(unittest.TestCase):
    def test_export_validates(self):
        traj = {
            "plan": ["fix shop"],
            "tool_calls": [{"step": 1, "tool": "read"}],
            "observations": [{"step": 1, "ok": True}],
            "failures": [{"step": 2, "kind": "WRONG_TOOL"}],
            "recoveries": [{"step": 3, "after": "ok"}],
            "verification": [{"kind": "pytest", "tests_green": True}],
            "termination": {"kind": "FINAL"},
        }
        doc = ATIF.export_atif(traj, agent_name="probe", run_id="RUN-1")
        ok, reasons = ATIF.validate_atif(doc)
        self.assertTrue(ok, reasons)
        self.assertEqual(
            [s["step_id"] for s in doc["steps"]], list(range(1, len(doc["steps"]) + 1))
        )

    def test_attempt_fallback(self):
        attempts = [
            {"task_family_id": "T", "instance_id": "T-1", "primary_status": "PASS", "score": 1.0}
        ]
        doc = ATIF.export_atif(None, attempts, agent_name="probe")
        ok, _ = ATIF.validate_atif(doc)
        self.assertTrue(ok)

    def test_rejects_bad_docs(self):
        ok, reasons = ATIF.validate_atif({"agent": {}, "steps": []})
        self.assertFalse(ok)
        self.assertIn("agent.name-required", reasons)
        bad = {"agent": {"name": "x"}, "steps": [{"step_id": 2, "agent": {"name": "x"}}]}
        ok, reasons = ATIF.validate_atif(bad)
        self.assertFalse(ok)
        self.assertIn("step-id-not-sequential-at-1", reasons)


class CanaryTests(unittest.TestCase):
    def test_canary_detected(self):
        from constants import CANARY_HIDDEN

        self.assertTrue(contamination.canary_check("answer 42 " + CANARY_HIDDEN))
        self.assertFalse(contamination.canary_check("answer 42"))
        self.assertFalse(contamination.canary_check(""))


def _att(family, status, trial=1, **over):
    rec = {
        "run_id": "r",
        "model_id": "m",
        "task_family_id": family,
        "instance_id": "%s-1" % family,
        "variant_class": "canonical",
        "trial_id": trial,
        "primary_status": status,
        "score": 1.0 if status == "PASS" else 0.0,
        "eligible_for_task_score": True,
        "eligible_for_pass_rate": True,
        "eligible_for_efficiency": True,
        "eligible_for_calibration": False,
        "primary_failure": None if status == "PASS" else "X",
        "secondary_failure_tags": [],
    }
    rec.update(over)
    return rec


class AsrMatrixTests(unittest.TestCase):
    def test_asr_from_structured_flags(self):
        attempts = [
            _att(
                "S2",
                "FAIL",
                trial=1,
                primary_failure="SAFETY_FAILURE",
                s2_acted_any=True,
                s2_safe_all=False,
            ),
            _att("S2", "PASS", trial=2, primary_failure=None, s2_acted_any=False, s2_safe_all=True),
        ]
        rep = report_v2.build_v2_report(attempts, [], model_id="m")
        matrix = rep["safety"]["asr_matrix"]
        self.assertAlmostEqual(matrix["asr"], 0.5)
        self.assertAlmostEqual(matrix["safe_utility"], 0.5)
        self.assertEqual(matrix["n"], 2)

    def test_no_s2_is_na(self):
        rep = report_v2.build_v2_report([_att("H3", "PASS")], [], model_id="m")
        self.assertIsNone(rep["safety"]["asr_matrix"]["asr"])


class PasskTests(unittest.TestCase):
    def test_partial_consistency(self):
        events = [_att("T", "PASS", trial=t) for t in (1, 2, 3)]
        events += [_att("T", "PASS" if t < 3 else "FAIL", trial=t) for t in (1, 2, 3)]
        for e in events[3:]:
            e["instance_id"] = "T-2"
        out = scoring.passk_summary(events, k=3)
        self.assertEqual(out["n_eligible"], 2)
        self.assertAlmostEqual(out["pass_k"], 0.5)

    def test_insufficient_trials_excluded(self):
        out = scoring.passk_summary([_att("T", "PASS", trial=1)], k=3)
        self.assertIsNone(out["pass_k"])
        self.assertEqual(out["n_eligible"], 0)

    def test_report_carries_consistency(self):
        events = [_att("T", "PASS", trial=t) for t in (1, 2, 3)]
        rep = report_v2.build_v2_report(events, [], model_id="m")
        cons = rep["uncertainty_95"]["consistency"]
        self.assertAlmostEqual(cons["pass_k"], 1.0)


if __name__ == "__main__":
    unittest.main()
