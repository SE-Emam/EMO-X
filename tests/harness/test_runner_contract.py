"""One authoritative runner contract (review P0-7).

`emo ...` delegates to shared/run.py; the legacy standalone entries
(security-bench/run_security.py, vision-bench/run_vision.py) are thin
wrappers over runner.run_suite, so every path emits standard sealed
raw bundles that pass the invariants gate.
"""

import importlib.util
import json
import os
import shutil
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
for _p in (ROOT, SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import invariants  # noqa: E402
import report_v2  # noqa: E402
import runner  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class RunnerContractTests(unittest.TestCase):
    def test_security_wrapper_emits_gated_bundle(self):
        sec = _load("sec_wrap_contract",
                    os.path.join(ROOT, "security-bench", "run_security.py"))
        out = "/tmp/emox_contract_sec"
        shutil.rmtree(out, ignore_errors=True)
        rc = sec.main(["--backend", "stub", "--only", "S1",
                       "--trials", "1", "--out", out])
        self.assertEqual(rc, 0)
        rundirs = [d for d in os.listdir(out)
                   if d.startswith("RUN-security")]
        self.assertEqual(len(rundirs), 1)
        events = [json.loads(line) for line in open(
            os.path.join(out, rundirs[0], "events.jsonl"))]
        self.assertTrue(events)
        invariants.validate_run_semantics(events)
        rep = report_v2.build_v2_report(events, [], model_id="m")
        self.assertIn("capability_profile", rep)

    def test_vision_wrapper_list_and_stub_bundle(self):
        vis = _load("vis_wrap_contract",
                    os.path.join(ROOT, "vision-bench", "run_vision.py"))
        self.assertEqual(vis.main(["--list"]), 0)
        out = "/tmp/emox_contract_vis"
        shutil.rmtree(out, ignore_errors=True)
        rc = vis.main(["--backend", "stub", "--only", "V4",
                       "--trials", "1", "--out", out])
        self.assertEqual(rc, 0)
        rundirs = [d for d in os.listdir(out)
                   if d.startswith("RUN-vision")]
        self.assertEqual(len(rundirs), 1)

    def test_emo_delegates_to_run_py(self):
        sys.path.insert(0, os.path.join(ROOT, "src"))
        import emox.cli as emo_cli
        with self.assertRaises(SystemExit) as ctx:
            emo_cli.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


class StreamingBundleTests(unittest.TestCase):
    def _manifest(self, run_id):
        return {"run_id": run_id, "suite": "s", "prompt_pack": "v1",
                "prompt_sha256": "a" * 64, "harness_sha256": "b" * 64,
                "model": "m", "backend": "stub", "seed": 0, "trials": 1}

    def _attempt(self, trial):
        return {"run_id": "r", "model_id": "m", "task_family_id": "T",
                "instance_id": "T-1", "variant_class": "canonical",
                "trial_id": trial, "primary_status": "FAIL", "score": 0.0,
                "primary_failure": "WRONG_RESULT"}

    def test_crash_leaves_no_partial_run_dir(self):
        out = "/tmp/emox_stream_test"
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        stream = runner.BundleStream(out, "RUN-crash")
        stream.append(self._attempt(1), {"reply": "x"})
        stream.abort()
        self.assertFalse(os.path.exists(os.path.join(out, "RUN-crash")))
        leftovers = [d for d in os.listdir(out) if "staging" in d]
        self.assertEqual(leftovers, [])

    def test_mismatch_fails_closed(self):
        out = "/tmp/emox_stream_test2"
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        with self.assertRaises(ValueError):
            runner.write_raw_bundle(
                out, self._manifest("RUN-mm"), [self._attempt(1)], [])


class UnsupportedVariantNATests(unittest.TestCase):
    def test_unsupported_variants_skipped_not_void(self):
        # code25 T5 supports canonical only: perturbed/novel must be
        # absent (NA per DEN), never VOID attempts corrupting coverage.
        out = "/tmp/emox_na_test"
        shutil.rmtree(out, ignore_errors=True)
        rundir, s = runner.run_suite(
            "code25", runner.stub_chat_factory("na-test"), "m", "stub",
            0, 1, 1, 0.25, out, families=["T5"])
        events = [json.loads(line) for line in open(
            os.path.join(rundir, "events.jsonl")) if line.strip()]
        self.assertTrue(events)
        for e in events:
            self.assertEqual(e["variant_class"], "canonical")
            self.assertNotEqual(e["primary_status"], "VOID")
        shutil.rmtree(out, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
