"""Sprint 2 golden tests: V7 (multi-image diff), V8 (spatial), V9 (chart).

Deterministic oracles only (no model calls). Executor integration is
covered via stub chats (force=True bypasses the vision gate).
Covers positive + negative paths per family plus the 5MB fail-closed
multi-image guard (VOID, never FAIL/ERROR for the model).

Run: python3 -m unittest discover -s tests/backends -v
"""

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
EXEC = _load("vis_executor_v7_v9_golden", os.path.join(VIS, "executor.py"))
VB = _load("vision_bench_v7_v9_golden", os.path.join(_ROOT, "vision-bench", "run_vision.py"))


def _vision_chat_factory(reply_text):
    def chat(messages, **kw):
        parts = (messages or [{}])[0].get("content", [])
        assert any(isinstance(p, dict) and p.get("type") == "image_url" for p in parts), (
            "vision message must carry an image part"
        )
        return reply_text, 0.5, {}

    return chat


class V7DiffGoldenTests(unittest.TestCase):
    def test_positive_correct_difference(self):
        j = VB.judge_diff("The middle square turned red", ["middle", "square", "red"])
        self.assertTrue(j["pass"])
        self.assertEqual(j["missing"], [])

    def test_negative_no_difference(self):
        j = VB.judge_diff("No difference at all", ["middle", "square", "red"])
        self.assertFalse(j["pass"])

    def test_negative_wrong_keywords(self):
        j = VB.judge_diff("The left circle is blue", ["middle", "square", "red"])
        self.assertFalse(j["pass"])

    def test_alias_center_box(self):
        j = VB.judge_diff("The center box turned red", ["middle", "square", "red"])
        self.assertTrue(j["pass"])

    def test_executor_v7_pass(self):
        chat = _vision_chat_factory("The middle square turned red")
        rec, _ = EXEC.run_family(
            "V7", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec["primary_status"], "PASS")

    def test_executor_v7_fail(self):
        chat = _vision_chat_factory("No difference at all")
        rec, _ = EXEC.run_family(
            "V7", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec["primary_status"], "FAIL")

    def test_multi_payload_guard_is_void(self):
        rec = VB.run_one_multi(
            _vision_chat_factory("x"),
            "diff",
            ["middle", "square", "red"],
            "p",
            ["/nonexistent/a.png"],
        )
        self.assertFalse(rec["pass"])
        self.assertTrue(rec.get("void"))
        self.assertIn("too large", rec.get("log", ""))


class V8SpatialGoldenTests(unittest.TestCase):
    def test_positive_arabic(self):
        self.assertTrue(VB.judge_spatial("الدائرة فوق المربع", "above")["pass"])

    def test_negative_wrong_preposition(self):
        self.assertFalse(VB.judge_spatial("الدائرة تحت المربع", "above")["pass"])

    def test_positive_english(self):
        self.assertTrue(VB.judge_spatial("The circle is above the square", "above")["pass"])

    def test_competing_relation_fails(self):
        j = VB.judge_spatial("above and below", "above")
        self.assertFalse(j["pass"])
        self.assertIn("below", j["competing"])

    def test_executor_v8_pass_fail(self):
        chat = _vision_chat_factory("الدائرة فوق المربع")
        rec, _ = EXEC.run_family(
            "V8", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec["primary_status"], "PASS")
        chat2 = _vision_chat_factory("الدائرة تحت المربع")
        rec2, _ = EXEC.run_family(
            "V8", chat2, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec2["primary_status"], "FAIL")


class V9ChartGoldenTests(unittest.TestCase):
    def test_positive_exact(self):
        self.assertTrue(VB.judge_chart("7", 7)["pass"])

    def test_negative_off_by_one(self):
        result = VB.judge_chart("6", 7)
        self.assertFalse(result["pass"])
        self.assertTrue(result["off_by_one"])

    def test_negative_invalid(self):
        result = VB.judge_chart("many", 7)
        self.assertFalse(result["pass"])
        self.assertTrue(result["invalid"])

    def test_executor_v9_pass_invalid_offbyone(self):
        chat = _vision_chat_factory("7")
        rec, _ = EXEC.run_family(
            "V9", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec["primary_status"], "PASS")
        chat2 = _vision_chat_factory("6")
        rec2, _ = EXEC.run_family(
            "V9", chat2, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec2["primary_status"], "FAIL")
        self.assertEqual(rec2.get("primary_failure"), "WRONG_RESULT (off_by_1)")
        chat3 = _vision_chat_factory("many")
        rec3, _ = EXEC.run_family(
            "V9", chat3, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec3["primary_status"], "INVALID")

    def test_dispatch_map_covers_v7_v9(self):
        for fam in ("V7", "V8", "V9"):
            self.assertIn(fam, EXEC.FAMILY_IDS)
            self.assertIn(fam, EXEC.FAMILY_TEST_MAP)
            self.assertTrue(EXEC.FAMILY_TEST_MAP[fam].startswith(fam + "_"))


if __name__ == "__main__":
    unittest.main()
