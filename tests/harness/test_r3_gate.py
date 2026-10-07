"""R3 official-baseline gate tests (stdlib unittest). SPEC B59.

Tests the R3 gate LOGIC via the pure `check_r3_gate` helper defined in
this file (no shared/ code is modified). Seal behavior is exercised
through the real `shared/seal.py` on synthetic temp bundles (read-only
use): a sealed bundle verifies, a tampered one does not.

R3 conditions: trials == 3, frozen seed 0, manifest recorded (SPEC 32
required fields), coverage >= 0.95, CSVRate == 0, seal valid.
Unknown coverage/CSVRate fails closed (ineligible).
"""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import seal

#: SPEC 32 required run-manifest fields (shared/schemas.py).
REQUIRED_MANIFEST_FIELDS = (
    "benchmark_version",
    "suite",
    "prompt_pack",
    "prompt_sha256",
    "harness_sha256",
    "model",
    "backend",
    "seed",
    "trials",
)

R3_TRIALS = 3
R3_SEED = 0
R3_MIN_COVERAGE = 0.95


def check_r3_gate(manifest, coverage, csv_rate, seal_ok, seal_reason=""):
    """Pure R3 gate check. Returns (ok, failures).

    manifest: dict (run manifest) or None when missing/unreadable.
    coverage: float or None (None = unknown => fail-closed).
    csv_rate: number or None (None = unknown => fail-closed).
    seal_ok: bool from seal.verify_bundle_seal; seal_reason: detail str.
    failures: list of failing condition names (empty when ok).
    """
    failures = []
    if not isinstance(manifest, dict):
        failures.append("manifest")
    else:
        missing = [k for k in REQUIRED_MANIFEST_FIELDS if k not in manifest]
        if missing:
            failures.append("manifest")
        if manifest.get("trials") != R3_TRIALS:
            failures.append("trials")
        if manifest.get("seed") != R3_SEED:
            failures.append("seed")
    if not isinstance(coverage, (int, float)) or coverage < R3_MIN_COVERAGE:
        failures.append("coverage")
    if csv_rate != 0:
        failures.append("csv_rate")
    if not seal_ok:
        failures.append("seal")
    return (len(failures) == 0, failures)


def good_manifest(**over):
    manifest = {
        "benchmark_version": "1.0",
        "suite": "code25",
        "prompt_pack": "PROMPT_PACK_v1",
        "prompt_sha256": "a" * 64,
        "harness_sha256": "b" * 64,
        "model": "stub-model",
        "backend": "stub",
        "seed": 0,
        "trials": 3,
    }
    manifest.update(over)
    return manifest


RAW_FILES = {
    "manifest.json": {"run_id": "R3-1"},
    "events.jsonl": '{"a": 1}\n',
    "responses.jsonl": '{"r": 1}\n',
    "environment.json": {"env": "test"},
}


def make_raw_bundle(root, run_id="R3-1", manifest=None):
    rundir = os.path.join(root, run_id)
    os.makedirs(rundir)
    for name, obj in RAW_FILES.items():
        if name == "manifest.json" and manifest is not None:
            obj = manifest
        path = os.path.join(rundir, name)
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(obj, str):
                f.write(obj)
            else:
                json.dump(obj, f)
    return rundir


def tamper(rundir, name="events.jsonl"):
    target = os.path.join(rundir, name)
    os.chmod(target, 0o644)
    with open(target, "ab") as f:
        f.write(b"tamper")


class TestR3GateLogic(unittest.TestCase):
    def test_good_bundle_passes(self):
        ok, failures = check_r3_gate(good_manifest(), 1.0, 0, True, "ok")
        self.assertEqual((ok, failures), (True, []))

    def test_trials_not_3_rejected(self):
        for trials in (1, 2, 4):
            ok, failures = check_r3_gate(good_manifest(trials=trials), 1.0, 0, True, "ok")
            self.assertFalse(ok, trials)
            self.assertIn("trials", failures)

    def test_seed_not_frozen_rejected(self):
        for seed in (1, 42):
            ok, failures = check_r3_gate(good_manifest(seed=seed), 1.0, 0, True, "ok")
            self.assertFalse(ok, seed)
            self.assertIn("seed", failures)

    def test_missing_manifest_rejected(self):
        ok, failures = check_r3_gate(None, 1.0, 0, True, "ok")
        self.assertFalse(ok)
        self.assertIn("manifest", failures)

    def test_manifest_missing_field_rejected(self):
        manifest = good_manifest()
        del manifest["prompt_sha256"]
        ok, failures = check_r3_gate(manifest, 1.0, 0, True, "ok")
        self.assertFalse(ok)
        self.assertIn("manifest", failures)

    def test_low_coverage_rejected(self):
        ok, failures = check_r3_gate(good_manifest(), 0.94, 0, True, "ok")
        self.assertFalse(ok)
        self.assertIn("coverage", failures)

    def test_unknown_coverage_rejected_fail_closed(self):
        ok, failures = check_r3_gate(good_manifest(), None, 0, True, "ok")
        self.assertFalse(ok)
        self.assertIn("coverage", failures)

    def test_nonzero_csv_rate_rejected(self):
        for csv in (0.01, 0.5, 1.0):
            ok, failures = check_r3_gate(good_manifest(), 1.0, csv, True, "ok")
            self.assertFalse(ok, csv)
            self.assertIn("csv_rate", failures)

    def test_unknown_csv_rate_rejected_fail_closed(self):
        ok, failures = check_r3_gate(good_manifest(), 1.0, None, True, "ok")
        self.assertFalse(ok)
        self.assertIn("csv_rate", failures)

    def test_bad_seal_rejected(self):
        ok, failures = check_r3_gate(good_manifest(), 1.0, 0, False, "tampered events.jsonl")
        self.assertFalse(ok)
        self.assertIn("seal", failures)

    def test_boundary_coverage_passes(self):
        ok, _ = check_r3_gate(good_manifest(), 0.95, 0, True, "ok")
        self.assertTrue(ok)

    def test_multiple_failures_all_reported(self):
        manifest = good_manifest(trials=1, seed=7)
        ok, failures = check_r3_gate(manifest, 0.5, 0.2, False, "unsealed")
        self.assertFalse(ok)
        self.assertEqual(set(failures), {"trials", "seed", "coverage", "csv_rate", "seal"})


class TestR3GateWithRealSeal(unittest.TestCase):
    """End-to-end gate verdicts over synthetic sealed bundles."""

    def _verdict(self, rundir, manifest, coverage, csv_rate):
        seal_ok, reason = seal.verify_bundle_seal(rundir)
        return check_r3_gate(manifest, coverage, csv_rate, seal_ok, reason)

    def test_sealed_bundle_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = good_manifest()
            rundir = make_raw_bundle(tmp, manifest=manifest)
            seal.seal_bundle(rundir)
            ok, failures = self._verdict(rundir, manifest, 1.0, 0)
            self.assertEqual((ok, failures), (True, []))

    def test_tampered_bundle_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = good_manifest()
            rundir = make_raw_bundle(tmp, manifest=manifest)
            seal.seal_bundle(rundir)
            tamper(rundir)
            ok, failures = self._verdict(rundir, manifest, 1.0, 0)
            self.assertFalse(ok)
            self.assertIn("seal", failures)

    def test_unsealed_bundle_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = good_manifest()
            rundir = make_raw_bundle(tmp, manifest=manifest)
            ok, failures = self._verdict(rundir, manifest, 1.0, 0)
            self.assertFalse(ok)
            self.assertIn("seal", failures)

    def test_sealed_but_wrong_trials_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = good_manifest(trials=1)
            rundir = make_raw_bundle(tmp, manifest=manifest)
            seal.seal_bundle(rundir)
            ok, failures = self._verdict(rundir, manifest, 1.0, 0)
            self.assertFalse(ok)
            self.assertIn("trials", failures)
            self.assertNotIn("seal", failures)

    def test_sealed_but_low_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = good_manifest()
            rundir = make_raw_bundle(tmp, manifest=manifest)
            seal.seal_bundle(rundir)
            ok, failures = self._verdict(rundir, manifest, 0.80, 0)
            self.assertFalse(ok)
            self.assertIn("coverage", failures)
            self.assertNotIn("seal", failures)


if __name__ == "__main__":
    unittest.main()
