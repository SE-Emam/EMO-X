"""Regression tests for fail-closed Latin font selection in Vision fixtures.

The harness test suite is stdlib-only; stub Pillow at import time so these tests
do not make the optional fixture-generation dependency a harness requirement.
"""

import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import patch

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
GENERATOR_PATH = os.path.join(ROOT, "vision-bench", "fixtures", "make_fixtures.py")


class _Mask:
    def __init__(self, value):
        self.size = (1, 1)
        self._bytes = value

    def __bytes__(self):
        return self._bytes


class _FakeFont:
    def __init__(self, missing="", space_advance=1.0):
        self.missing = set(missing)
        self.space_advance = space_advance

    def getmask(self, char):
        if char == "\U0010ffff" or char in self.missing:
            return _Mask(b"\x00")
        return _Mask(bytes([(ord(char) % 254) + 1]))

    def getlength(self, char):
        return self.space_advance if char == " " else 1.0


def _load_generator_with_stub_pillow():
    # Only import-time names are needed by these tests; no image generation is
    # executed. This prevents optional Pillow from becoming a CI requirement.
    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = object()
    fake_pil.ImageDraw = object()
    fake_pil.ImageFont = types.SimpleNamespace(truetype=lambda *_args, **_kwargs: None)
    fake_pil.features = types.SimpleNamespace(check=lambda *_args, **_kwargs: False)
    spec = importlib.util.spec_from_file_location(
        "_emox_vision_fixture_generator_test", GENERATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Vision fixture generator for unit tests")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"PIL": fake_pil}):
        spec.loader.exec_module(module)
    return module


class LatinFontSelectionTests(unittest.TestCase):
    def test_selection_rejects_missing_glyphs_and_fails_closed(self):
        generator = _load_generator_with_stub_pillow()
        generator.LATIN_FONT_CANDIDATES = ["/font/incomplete.ttf", "/font/complete.ttf"]

        # The first existing font loads, but it cannot render a required glyph;
        # the selector must continue to the next deterministic candidate.
        with (
            patch.object(generator.os.path, "isfile", return_value=True),
            patch.object(
                generator.ImageFont,
                "truetype",
                side_effect=[_FakeFont(missing="G"), _FakeFont()],
            ),
        ):
            self.assertEqual(generator.find_latin_font(), "/font/complete.ttf")

        # If every candidate lacks required glyph coverage, generation must
        # fail loudly rather than writing silently corrupted frozen fixtures.
        with (
            patch.object(generator.os.path, "isfile", return_value=True),
            patch.object(
                generator.ImageFont,
                "truetype",
                side_effect=[_FakeFont(missing="G"), _FakeFont(missing="x")],
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "glyph coverage"):
                generator.find_latin_font()


if __name__ == "__main__":
    unittest.main()
