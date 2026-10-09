"""Sprint 1 vision normalization utils (stdlib unittest).

Covers shared/scoring.py normalize_arabic / normalize_int / iou_tier.
Deterministic only; mirrors vision-bench/run_vision.py copies.

Run: python3 -m unittest discover -s tests/scoring -v
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


class TestNormalizeArabic(unittest.TestCase):
    def test_strips_tashkeel(self):
        self.assertEqual(scoring.normalize_arabic("تَسْجِيل"), "تسجيل")

    def test_alef_variants(self):
        self.assertEqual(scoring.normalize_arabic("أحمر"), scoring.normalize_arabic("احمر"))

    def test_teh_marbuta(self):
        # ة normalizes to ه for robust OCR substring matching.
        self.assertEqual(scoring.normalize_arabic("مدرسة"), "مدرسه")
        self.assertEqual(scoring.normalize_arabic("سبعة"), scoring.normalize_arabic("سبعه"))

    def test_none_empty(self):
        self.assertEqual(scoring.normalize_arabic(None), "")
        self.assertEqual(scoring.normalize_arabic("  "), "")

    def test_whitespace_collapse(self):
        self.assertEqual(scoring.normalize_arabic("تسجيل   الدخول"), "تسجيل الدخول")


class TestNormalizeInt(unittest.TestCase):
    def test_digits(self):
        self.assertEqual(scoring.normalize_int("7"), 7)
        self.assertEqual(scoring.normalize_int("There are 4 red squares."), 4)

    def test_english_words(self):
        self.assertEqual(scoring.normalize_int("seven"), 7)
        self.assertEqual(scoring.normalize_int("I see THREE buttons"), 3)

    def test_arabic_indic(self):
        self.assertEqual(scoring.normalize_int("٧"), 7)

    def test_arabic_words(self):
        self.assertEqual(scoring.normalize_int("سبعة"), 7)
        self.assertEqual(scoring.normalize_int("العدد سبعه"), 7)

    def test_none_when_absent(self):
        self.assertIsNone(scoring.normalize_int("no number here"))
        self.assertIsNone(scoring.normalize_int(None))
        self.assertIsNone(scoring.normalize_int(""))


class TestIouTier(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(scoring.iou_tier(0.95), 0.9)
        self.assertEqual(scoring.iou_tier(0.82), 0.7)
        self.assertEqual(scoring.iou_tier(0.55), 0.5)
        self.assertEqual(scoring.iou_tier(0.3), 0.0)
        self.assertEqual(scoring.iou_tier(None), 0.0)


if __name__ == "__main__":
    unittest.main()
