"""Tests for shared/adaptive.py (stdlib unittest). SPEC 10.

Covers: rung labels + bounds, variant mapping (D6/D7 share "novel" —
no dedicated compound variant, pinned intentionally), promote/demote
streaks, floor-diagnose rule, bump-aware recommendation, and the
ability curve with NA (None) for unobserved rungs.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import adaptive as A  # noqa: E402


class DifficultyLabelTests(unittest.TestCase):
    def test_all_rungs_labeled(self):
        self.assertEqual(A.difficulty_label(0), "trivial")
        self.assertEqual(A.difficulty_label(7), "long-horizon")
        self.assertEqual(len(A.DIFFICULTY_LABELS), 8)

    def test_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            A.difficulty_label(-1)
        with self.assertRaises(ValueError):
            A.difficulty_label(8)


class VariantMappingTests(unittest.TestCase):
    def test_ladder(self):
        self.assertEqual(A.variant_for_difficulty(0), "canonical")
        self.assertEqual(A.variant_for_difficulty(1), "canonical")
        self.assertEqual(A.variant_for_difficulty(2), "structural")
        self.assertEqual(A.variant_for_difficulty(3), "constraint")
        self.assertEqual(A.variant_for_difficulty(4), "adversarial")
        self.assertEqual(A.variant_for_difficulty(5), "recovery")

    def test_compound_rungs_share_novel(self):
        # No dedicated "compound" variant exists; D6/D7 both map to
        # "novel" by design (pinned here so any change is deliberate).
        self.assertEqual(A.variant_for_difficulty(6), "novel")
        self.assertEqual(A.variant_for_difficulty(7), "novel")


class ControllerTests(unittest.TestCase):
    def _ctl(self, outcomes, difficulty=1):
        ctl = A.AdaptiveController()
        for ok in outcomes:
            ctl.observe("H3", difficulty=difficulty, passed=ok)
        return ctl

    def test_promote_on_streak(self):
        ctl = self._ctl([True, True])
        nxt, action, _ = ctl.recommend("H3", difficulty=1)
        self.assertEqual((nxt, action), (2, "promote"))

    def test_hold_below_streak(self):
        ctl = self._ctl([True])
        nxt, action, _ = ctl.recommend("H3", difficulty=1)
        self.assertEqual((nxt, action), (1, "hold"))

    def test_demote_on_fail_streak(self):
        ctl = self._ctl([False, False])
        nxt, action, _ = ctl.recommend("H3", difficulty=3)
        self.assertEqual((nxt, action), (2, "demote"))

    def test_floor_diagnose_not_below_d0(self):
        ctl = self._ctl([False, False, False])
        nxt, action, _ = ctl.recommend("H3", difficulty=0)
        self.assertEqual((nxt, action), (0, "diagnose"))

    def test_bump_shifts_effective_rung(self):
        # A hard variant (recovery, bump 3) at D1 behaves like D4:
        # two passes still promote from the nominal rung.
        ctl = self._ctl([True, True])
        nxt, action, variant = ctl.recommend(
            "H3", difficulty=1, variant="recovery")
        self.assertEqual(action, "promote")
        self.assertEqual(nxt, 2)
        self.assertEqual(variant, "structural")

    def test_observe_validates_rung(self):
        ctl = A.AdaptiveController()
        with self.assertRaises(ValueError):
            ctl.observe("H3", difficulty=9, passed=True)


class AbilityCurveTests(unittest.TestCase):
    def test_unobserved_rungs_are_none(self):
        ctl = A.AdaptiveController()
        ctl.observe("H3", difficulty=1, passed=True)
        curve = ctl.ability_curve("H3")
        self.assertEqual(curve[1], 1.0)
        for rung in (0, 2, 3, 4, 5, 6, 7):
            self.assertIsNone(curve[rung])
        self.assertEqual(curve["summary"]["n_observed"], 1)
        self.assertEqual(curve["summary"]["best_rung"], 1)

    def test_empty_family(self):
        curve = A.AdaptiveController().ability_curve("never-seen")
        self.assertIsNone(curve["summary"]["best_rung"])
        self.assertEqual(curve["summary"]["n_observed"], 0)


if __name__ == "__main__":
    unittest.main()
