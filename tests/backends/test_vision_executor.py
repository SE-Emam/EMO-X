"""Tests for the real vision executor (gate + oracles + hashes)."""

import importlib.util
import os
import sys
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


VIS = os.path.join(_ROOT, "suites", "vision")
EXEC = _load("vis_executor_tests",
             os.path.join(VIS, "executor.py"))


def _no_image_chat(messages, **kw):
    raise RuntimeError("unsupported content: image_url parts rejected")


def _vision_chat_factory(reply_text):
    def chat(messages, **kw):
        parts = (messages or [{}])[0].get("content", [])
        assert any(isinstance(p, dict) and p.get("type") == "image_url"
                   for p in parts), "vision message must carry an image part"
        return reply_text, 0.5, {}
    return chat


class VisionGateTests(unittest.TestCase):
    def test_gate_failure_is_void_not_fail(self):
        rec, resp = EXEC.run_family("V1", _no_image_chat, run_id="R",
                                    model_id="m", trial_id=1, base_url="")
        self.assertEqual(rec["primary_status"], "VOID")
        self.assertFalse(rec["eligible_for_task_score"])
        self.assertIn("vision-gate", rec.get("error", ""))
        self.assertTrue(resp.get("void"))

    def test_bad_variant_raises(self):
        with self.assertRaises(TypeError):
            EXEC.run_family("V1", _no_image_chat, run_id="R",
                            model_id="m", trial_id=1, variant="novel",
                            base_url="", force=True)

    def test_unknown_family_raises(self):
        with self.assertRaises(KeyError):
            EXEC.run_family("V9", _no_image_chat, run_id="R",
                            model_id="m", trial_id=1, base_url="",
                            force=True)


class VisionOracleTests(unittest.TestCase):
    def test_count_pass(self):
        chat = _vision_chat_factory("7")
        rec, _ = EXEC.run_family("V4", chat, run_id="R", model_id="m",
                                 trial_id=1, base_url="", force=True)
        self.assertEqual(rec["primary_status"], "PASS")
        self.assertEqual(rec["score"], 1.0)

    def test_count_fail(self):
        chat = _vision_chat_factory("5")
        rec, _ = EXEC.run_family("V4", chat, run_id="R", model_id="m",
                                 trial_id=1, base_url="", force=True)
        self.assertEqual(rec["primary_status"], "FAIL")

    def test_arabic_keywords(self):
        chat = _vision_chat_factory("تسجيل الدخول مرحبا")
        rec, _ = EXEC.run_family("V3", chat, run_id="R", model_id="m",
                                 trial_id=1, base_url="", force=True)
        self.assertEqual(rec["primary_status"], "PASS")

    def test_hashes_stable(self):
        h1, h2 = EXEC.prompt_pack_sha256(), EXEC.prompt_pack_sha256()
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)
        hh = EXEC.harness_sha256()
        self.assertEqual(len(hh), 64)


if __name__ == "__main__":
    unittest.main()
