"""Tests for the realworld suite (mini-real tasks + vision executor)."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


RW = _load("rw_executor_tests",
           os.path.join(_ROOT, "suites", "realworld", "executor.py"))
VIS = _load("vis_executor_tests2",
            os.path.join(_ROOT, "suites", "vision", "executor.py"))


class RealworldFixtureTests(unittest.TestCase):
    def test_all_fixtures_fail_before_fix(self):
        """Every family must fail pytest pre-fix (real bugs, not toys)."""
        for fam in ("RW1", "RW2", "RW3"):
            root = tempfile.mkdtemp()
            try:
                RW.build_fixture(fam, root)
                p = subprocess.run(
                    ["python3", "-m", "pytest", "tests/", "-q"],
                    cwd=root, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(
                    p.returncode, 0, "%s passes pre-fix (not a real bug)" % fam)
            finally:
                import shutil
                shutil.rmtree(root, ignore_errors=True)

    def test_manifests_validate(self):
        for fam in ("RW1", "RW2", "RW3"):
            m = RW.load_manifest(fam)
            self.assertEqual(m["id"], fam)
            self.assertGreater(m["estimated_human_minutes"], 0)

    def test_bad_variant_raises(self):
        with self.assertRaises(TypeError):
            RW.run_family("RW1", None, run_id="R", model_id="m",
                          trial_id=1, variant="novel")

    def test_hashes_stable(self):
        self.assertEqual(RW.prompt_pack_sha256(),
                         RW.prompt_pack_sha256())
        self.assertEqual(len(RW.harness_sha256()), 64)


class VisionExecutorTests(unittest.TestCase):
    def test_gate_void(self):
        def chat(messages, **kw):
            raise RuntimeError("unsupported content: no image parts")
        rec, resp = VIS.run_family("V1", chat, run_id="R", model_id="m",
                                   trial_id=1, base_url="")
        self.assertEqual(rec["primary_status"], "VOID")
        self.assertTrue(resp.get("void"))

    def test_oracle_count(self):
        def chat(messages, **kw):
            return "7", 0.5, {}
        rec, _ = VIS.run_family("V4", chat, run_id="R", model_id="m",
                                trial_id=1, base_url="", force=True)
        self.assertEqual(rec["primary_status"], "PASS")

    def test_hashes_stable(self):
        self.assertEqual(VIS.prompt_pack_sha256(),
                         VIS.prompt_pack_sha256())
        self.assertEqual(len(VIS.harness_sha256()), 64)


if __name__ == "__main__":
    unittest.main()
