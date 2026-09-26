"""Tests for the hero splash screen (structure locked, values live)."""

import io
import os
import re
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from splash import (banner, collect_stats, print_banner,  # noqa: E402
                    should_show, LOGO_LINES, TAGLINE)

ANSI_RE = re.compile(r"\x1b\[[0-9]+m")


def _plain(text):
    return ANSI_RE.sub("", text)


class SplashStructureTests(unittest.TestCase):
    def test_frame_intact(self):
        out = banner(width=100, color=False)
        lines = out.splitlines()
        self.assertTrue(lines[0].strip().startswith("╔"))
        self.assertTrue(lines[-1].strip().startswith("╚"))
        # All frame lines share one indent (centered as a block).
        indents = {len(l) - len(l.lstrip())
                   for l in lines if l.strip()[:1] in "╔║╚"}
        self.assertEqual(len(indents), 1)

    def test_logo_and_tagline_present(self):
        out = _plain(banner(width=100, color=False))
        for logo_line in LOGO_LINES:
            self.assertIn(logo_line.strip()[:12], out)
        self.assertIn(TAGLINE, out)

    def test_compact_fallback_narrow(self):
        out = banner(width=40, color=False)
        self.assertIn("EMO-X", out)
        self.assertNotIn("╔", out)

    def test_no_color_when_requested(self):
        out = banner(width=100, color=True)
        self.assertIn("\x1b[94m", out)  # blue logo
        plain = banner(width=100, color=False)
        self.assertNotIn("\x1b[", plain)


class SplashDynamicTests(unittest.TestCase):
    def test_counts_come_from_tree(self):
        stats = collect_stats()
        self.assertRegex(str(stats["version"]), r"\d+\.\d+")
        self.assertGreater(stats["suites"], 5)
        self.assertGreater(stats["manifests"], 50)
        self.assertGreater(stats["tests"], 300)

    def test_banner_embeds_live_counts(self):
        stats = {"version": "9.9.9", "suites": 1, "manifests": 2,
                 "tests": 3}
        out = _plain(banner(stats=stats, width=100, color=False))
        self.assertIn("v9.9.9", out)
        self.assertIn("1 suites", out)


class SplashBehaviorTests(unittest.TestCase):
    def test_quiet_flag(self):
        self.assertFalse(should_show(args=["--quiet"]))
        self.assertFalse(should_show(args=["-q"]))
        self.assertTrue(should_show(args=[]))

    def test_print_goes_to_stderr_not_stdout(self):
        err = io.StringIO()
        text = print_banner(stream=err, width=100)
        # Block-letter logo carries no literal "EMO-X"; tagline does.
        self.assertIn(TAGLINE, _plain(text))
        self.assertGreater(len(err.getvalue()), 100)

    def test_disabled_returns_empty(self):
        err = io.StringIO()
        self.assertEqual(print_banner(stream=err, enabled=False), "")
        self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
