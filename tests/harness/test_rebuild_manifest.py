"""Tests for manifest rebuildability (Y-9, docs-only + this file).

Covers shared/runner.py::build_manifest + collect_environment:
every documented manifest field present, environment/toolchain
complete and unknown-tolerant, model_sha256 stable, run_ids unique,
manifests schema-valid. Stdlib unittest only.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import runner
import schemas

MANIFEST_FIELDS = (
    "benchmark_version",
    "suite",
    "prompt_pack",
    "prompt_sha256",
    "harness_sha256",
    "harness_git_sha",
    "backend",
    "provider_profile",
    "backend_capabilities",
    "model",
    "model_sha256",
    "temperature",
    "top_p",
    "top_k",
    "context",
    "seed",
    "trials",
    "run_id",
    "timestamp_utc",
    "runner_version",
)

ENV_FIELDS = (
    "python",
    "platform",
    "architecture",
    "toolchain",
    "harness_git_sha",
    "written_utc",
)

TOOLCHAIN_FIELDS = ("python", "node", "rustc", "tsc", "sqlite", "postgres")


def make_manifest(run_id, model="stub-model", seed=1234):
    return runner.build_manifest(
        "code25",
        "a" * 64,
        "b" * 64,
        model,
        "stub",
        seed,
        2,
        run_id,
        sampling={"temperature": 0.4, "top_p": 0.9, "top_k": 40, "context": 8192},
    )


class TestRebuildManifest(unittest.TestCase):
    def test_all_manifest_fields_present(self):
        m = make_manifest(runner.make_run_id("RUN-t"))
        for field in MANIFEST_FIELDS:
            self.assertIn(field, m, "manifest missing: %s" % field)

    def test_environment_fields_present(self):
        env = runner.collect_environment()
        for field in ENV_FIELDS:
            self.assertIn(field, env, "environment missing: %s" % field)
        for field in TOOLCHAIN_FIELDS:
            self.assertIn(field, env["toolchain"], "toolchain missing: %s" % field)

    def test_toolchain_unknown_tolerant(self):
        tc = runner.collect_toolchain()  # must never raise
        env = runner.collect_environment()  # must never raise
        self.assertIs(tc, tc)  # smoke: call succeeded
        for field in TOOLCHAIN_FIELDS:
            val = tc[field]
            self.assertIsInstance(val, str, field)
            self.assertTrue(val, "toolchain.%s must never be empty" % field)
            self.assertIsInstance(env["toolchain"][field], str, field)
            self.assertTrue(env["toolchain"][field], "env toolchain.%s empty" % field)

    def test_model_sha256_stable(self):
        a = make_manifest("RUN-x-1", model="stub-model")
        b = make_manifest("RUN-x-2", model="stub-model")
        self.assertEqual(a["model_sha256"], b["model_sha256"])
        self.assertEqual(len(a["model_sha256"]), 64)
        other = make_manifest("RUN-x-3", model="other-model")
        self.assertNotEqual(a["model_sha256"], other["model_sha256"])

    def test_run_twice_different_run_ids_valid(self):
        r1 = runner.make_run_id("RUN-stub")
        r2 = runner.make_run_id("RUN-stub")
        self.assertNotEqual(r1, r2)
        m1 = make_manifest(r1)
        m2 = make_manifest(r2)
        self.assertNotEqual(m1["run_id"], m2["run_id"])
        schemas.validate_run_manifest(m1)  # valid manifests
        schemas.validate_run_manifest(m2)
        env = runner.collect_environment()
        self.assertTrue(env["written_utc"])
        self.assertTrue(env["harness_git_sha"])


if __name__ == "__main__":
    unittest.main()
