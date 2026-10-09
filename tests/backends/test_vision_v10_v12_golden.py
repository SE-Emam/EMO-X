"""Sprint 3 golden tests: V10 (noisy grounding), V11 (dense count), V12 (table).

Deterministic oracles only (no model calls). Executor integration is
covered via stub chats (force=True bypasses the vision gate).
Covers positive + negative paths per family plus flag-gated PARTIAL
tier scoring (default OFF keeps binary PASS/FAIL/INVALID).

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
EXEC = _load("vis_executor_v10_v12_golden", os.path.join(VIS, "executor.py"))
VB = _load("vision_bench_v10_v12_golden", os.path.join(_ROOT, "vision-bench", "run_vision.py"))
SCORING = _load("vision_scoring_v10_v12_golden", os.path.join(_ROOT, "shared", "scoring.py"))

# GT login box (ui_login_noisy.png): [x0,y0,x1,y1] = [175,633,425,717].
EXACT_BOX_JSON = '{"x": 175, "y": 633, "w": 250, "h": 84}'
# +50px x-shift -> IoU ~0.667 (tier 0.5 band).
SHIFT50_BOX_JSON = '{"x": 225, "y": 633, "w": 250, "h": 84}'
# +20px x-shift -> IoU ~0.852 (tier 0.75 band).
SHIFT20_BOX_JSON = '{"x": 195, "y": 633, "w": 250, "h": 84}'
FAR_BOX_JSON = '{"x": 600, "y": 100, "w": 100, "h": 100}'


def _vision_chat_factory(reply_text):
    def chat(messages, **kw):
        parts = (messages or [{}])[0].get("content", [])
        assert any(isinstance(p, dict) and p.get("type") == "image_url" for p in parts), (
            "vision message must carry an image part"
        )
        return reply_text, 0.5, {}

    return chat


class V10NoisyGroundingGoldenTests(unittest.TestCase):
    def test_exact_box_pass_binary(self):
        chat = _vision_chat_factory(EXACT_BOX_JSON)
        rec, _ = EXEC.run_family(
            "V10", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec["primary_status"], "PASS")
        self.assertEqual(rec["score"], 1.0)

    def test_exact_box_pass_partial_curve(self):
        chat = _vision_chat_factory(EXACT_BOX_JSON)
        rec, _ = EXEC.run_family(
            "V10",
            chat,
            run_id="R",
            model_id="m",
            trial_id=1,
            base_url="",
            force=True,
            partial_curve=True,
        )
        self.assertEqual(rec["primary_status"], "PASS")
        self.assertEqual(rec["score"], 1.0)

    def test_shifted_box_pass_binary_partial_with_flag(self):
        chat = _vision_chat_factory(SHIFT50_BOX_JSON)
        rec_bin, _ = EXEC.run_family(
            "V10", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec_bin["primary_status"], "PASS")
        rec_part, _ = EXEC.run_family(
            "V10",
            chat,
            run_id="R",
            model_id="m",
            trial_id=1,
            base_url="",
            force=True,
            partial_curve=True,
        )
        self.assertEqual(rec_part["primary_status"], "PARTIAL")
        self.assertEqual(rec_part["score"], 0.5)
        self.assertTrue(rec_part.get("primary_failure", "").startswith("PARTIAL_IOU"))

    def test_shifted20_box_partial_075(self):
        chat = _vision_chat_factory(SHIFT20_BOX_JSON)
        rec, _ = EXEC.run_family(
            "V10",
            chat,
            run_id="R",
            model_id="m",
            trial_id=1,
            base_url="",
            force=True,
            partial_curve=True,
        )
        self.assertEqual(rec["primary_status"], "PARTIAL")
        self.assertEqual(rec["score"], 0.75)

    def test_far_box_fail_both_modes(self):
        for flag in (False, True):
            chat = _vision_chat_factory(FAR_BOX_JSON)
            rec, _ = EXEC.run_family(
                "V10",
                chat,
                run_id="R",
                model_id="m",
                trial_id=1,
                base_url="",
                force=True,
                partial_curve=flag,
            )
            self.assertEqual(rec["primary_status"], "FAIL")

    def test_run_one_grounding_tier_scores(self):
        gt = [175, 633, 425, 717]
        img = os.path.join(_ROOT, "vision-bench", "fixtures", "ui_login_noisy.png")
        rec = VB.run_one(
            _vision_chat_factory(SHIFT50_BOX_JSON),
            "ground",
            gt,
            "p",
            img,
            partial_curve=True,
        )
        self.assertTrue(rec["pass"])
        self.assertEqual(rec["score"], 0.5)


class V11DenseCountGoldenTests(unittest.TestCase):
    def test_positive_exact_12(self):
        self.assertTrue(VB.judge_count("12", 12)["pass"])
        chat = _vision_chat_factory("12")
        rec, _ = EXEC.run_family(
            "V11", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec["primary_status"], "PASS")

    def test_off_by_one_binary_fail_partial_with_flag(self):
        j = VB.judge_count("11", 12)
        self.assertFalse(j["pass"])
        self.assertTrue(j["off_by_one"])
        chat = _vision_chat_factory("11")
        rec_bin, _ = EXEC.run_family(
            "V11", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec_bin["primary_status"], "FAIL")
        self.assertEqual(rec_bin.get("primary_failure"), "WRONG_RESULT (off_by_1)")
        rec_part, _ = EXEC.run_family(
            "V11",
            chat,
            run_id="R",
            model_id="m",
            trial_id=1,
            base_url="",
            force=True,
            partial_curve=True,
        )
        self.assertEqual(rec_part["primary_status"], "PARTIAL")
        self.assertEqual(rec_part["score"], 0.5)
        self.assertEqual(rec_part.get("primary_failure"), "PARTIAL_OFF_BY_ONE")

    def test_invalid_no_int_never_partial(self):
        chat = _vision_chat_factory("many circles")
        for flag in (False, True):
            rec, _ = EXEC.run_family(
                "V11",
                chat,
                run_id="R",
                model_id="m",
                trial_id=1,
                base_url="",
                force=True,
                partial_curve=flag,
            )
            self.assertEqual(rec["primary_status"], "INVALID")

    def test_run_one_count_partial_scores(self):
        img = os.path.join(_ROOT, "vision-bench", "fixtures", "grid_dense.png")
        rec_off = VB.run_one(_vision_chat_factory("11"), "count", 12, "p", img, partial_curve=True)
        self.assertEqual(rec_off["score"], 0.5)
        rec_bin = VB.run_one(_vision_chat_factory("11"), "count", 12, "p", img, partial_curve=False)
        self.assertEqual(rec_bin["score"], 0.0)


class V12TableGoldenTests(unittest.TestCase):
    def test_positive_exact(self):
        self.assertTrue(VB.judge_table("3,15", 3, 15)["pass"])
        chat = _vision_chat_factory("3,15")
        rec, _ = EXEC.run_family(
            "V12", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec["primary_status"], "PASS")

    def test_positive_verbose_form(self):
        self.assertTrue(VB.judge_table("rows 3 amount 15", 3, 15)["pass"])

    def test_negative_wrong_amount(self):
        j = VB.judge_table("3,16", 3, 15)
        self.assertFalse(j["pass"])
        self.assertTrue(j["off_by_one"])

    def test_negative_invalid(self):
        j = VB.judge_table("no numbers here", 3, 15)
        self.assertFalse(j["pass"])
        self.assertTrue(j["invalid"])

    def test_executor_off_by_one_partial_with_flag(self):
        chat = _vision_chat_factory("3,16")
        rec_bin, _ = EXEC.run_family(
            "V12", chat, run_id="R", model_id="m", trial_id=1, base_url="", force=True
        )
        self.assertEqual(rec_bin["primary_status"], "FAIL")
        self.assertEqual(rec_bin.get("primary_failure"), "WRONG_RESULT (off_by_1)")
        rec_part, _ = EXEC.run_family(
            "V12",
            chat,
            run_id="R",
            model_id="m",
            trial_id=1,
            base_url="",
            force=True,
            partial_curve=True,
        )
        self.assertEqual(rec_part["primary_status"], "PARTIAL")
        self.assertEqual(rec_part["score"], 0.5)

    def test_executor_invalid_never_partial(self):
        chat = _vision_chat_factory("no numbers here")
        for flag in (False, True):
            rec, _ = EXEC.run_family(
                "V12",
                chat,
                run_id="R",
                model_id="m",
                trial_id=1,
                base_url="",
                force=True,
                partial_curve=flag,
            )
            self.assertEqual(rec["primary_status"], "INVALID")

    def test_dispatch_map_covers_v10_v12(self):
        for fam in ("V10", "V11", "V12"):
            self.assertIn(fam, EXEC.FAMILY_IDS)
            self.assertIn(fam, EXEC.FAMILY_TEST_MAP)
            self.assertTrue(EXEC.FAMILY_TEST_MAP[fam].startswith(fam + "_"))


class PartialScoringUnitTests(unittest.TestCase):
    def test_iou_partial_tiers(self):
        self.assertEqual(SCORING.iou_partial_score(0.95), 1.0)
        self.assertEqual(SCORING.iou_partial_score(0.8), 0.75)
        self.assertEqual(SCORING.iou_partial_score(0.6), 0.5)
        self.assertEqual(SCORING.iou_partial_score(0.3), 0.0)
        self.assertEqual(SCORING.iou_partial_score(None), 0.0)

    def test_vision_grounding_score_binary_vs_partial(self):
        self.assertEqual(SCORING.vision_grounding_score(0.6), 1.0)
        self.assertEqual(SCORING.vision_grounding_score(0.6, partial_curve=True), 0.5)
        self.assertEqual(SCORING.vision_grounding_score(0.3, partial_curve=True), 0.0)

    def test_vision_count_score(self):
        self.assertEqual(SCORING.vision_count_score(True), 1.0)
        self.assertEqual(SCORING.vision_count_score(False, off_by_one=True), 0.0)
        self.assertEqual(
            SCORING.vision_count_score(False, off_by_one=True, partial_curve=True),
            0.5,
        )

    def test_vision_partial_status(self):
        self.assertEqual(SCORING.vision_partial_status(1.0, True), "PASS")
        self.assertEqual(SCORING.vision_partial_status(0.5, True), "PARTIAL")
        self.assertEqual(SCORING.vision_partial_status(0.5, False), "PARTIAL")
        self.assertEqual(SCORING.vision_partial_status(0.0, False), "FAIL")
        self.assertEqual(SCORING.vision_partial_status(0.0, False, invalid=True), "INVALID")


if __name__ == "__main__":
    unittest.main()
