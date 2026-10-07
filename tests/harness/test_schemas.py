"""Tests for shared/schemas.py (stdlib unittest). DEN C4, C83, C90-C91."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(os.path.dirname(HERE), "..", "shared")
SHARED = os.path.normpath(SHARED)
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import schemas


def good_attempt():
    return {
        "run_id": "r1",
        "model_id": "m1",
        "task_family_id": "H3",
        "instance_id": "H3-00017",
        "variant_class": "structural",
        "trial_id": 2,
        "primary_status": "PASS",
        "score": 1.0,
        "eligible_for_task_score": True,
        "eligible_for_pass_rate": True,
        "eligible_for_efficiency": True,
        "eligible_for_calibration": False,
        "primary_failure": None,
        "secondary_failure_tags": [],
    }


def good_run_manifest():
    return {
        "benchmark_version": "2.0.0",
        "suite": "code-bench-25",
        "prompt_pack": "PROMPT_PACK_v2",
        "prompt_sha256": "a" * 64,
        "harness_sha256": "b" * 64,
        "model": "m1",
        "backend": "local",
        "seed": 12345,
        "trials": 3,
    }


def good_task_manifest():
    return {
        "id": "H3",
        "version": "1.0",
        "name": "modular_arithmetic",
        "category": "reasoning",
        "capabilities": ["generalization"],
        "generator": {"type": "parametric"},
        "difficulty": {"base": 3},
        "execution": {"type": "python"},
        "oracle": {"type": "deterministic"},
        "scoring": {"correctness": 1.0},
        "variants": ["canonical"],
        "timeouts": {"execution_seconds": 30},
        "network": {"allowed": False},
        "filesystem": {"sandbox_only": True},
    }


class TestAttempt(unittest.TestCase):
    def test_valid(self):
        out = schemas.validate_attempt(good_attempt())
        self.assertEqual(out["score"], 1.0)

    def test_missing_trial_id(self):
        rec = good_attempt()
        del rec["trial_id"]
        with self.assertRaises(schemas.SchemaError):
            schemas.validate_attempt(rec)

    def test_bad_status(self):
        rec = good_attempt()
        rec["primary_status"] = "BROKEN"
        with self.assertRaises(schemas.SchemaError):
            schemas.validate_attempt(rec)

    def test_score_out_of_range(self):
        for bad in (-0.1, 1.5, "high"):
            rec = good_attempt()
            rec["score"] = bad
            with self.assertRaises(schemas.SchemaError, msg=repr(bad)):
                schemas.validate_attempt(rec)

    def test_identity(self):
        rec = good_attempt()
        self.assertEqual(schemas.attempt_identity(rec), ("r1", "H3", "H3-00017", 2))

    def test_na_or_zero(self):
        self.assertIsNone(schemas.na_or_zero(0, 0))
        self.assertEqual(schemas.na_or_zero(2, 1), 0.5)


class TestManifests(unittest.TestCase):
    def test_run_manifest_valid(self):
        schemas.validate_run_manifest(good_run_manifest())

    def test_run_manifest_missing(self):
        rec = good_run_manifest()
        del rec["seed"]
        with self.assertRaises(schemas.SchemaError):
            schemas.validate_run_manifest(rec)

    def test_task_manifest_valid(self):
        schemas.validate_task_manifest(good_task_manifest())

    def test_task_manifest_missing(self):
        rec = good_task_manifest()
        del rec["oracle"]
        with self.assertRaises(schemas.SchemaError):
            schemas.validate_task_manifest(rec)


if __name__ == "__main__":
    unittest.main()
