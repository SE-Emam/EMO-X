"""Tests for render_security_board.py (v1 flat security JSONs)."""

import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from render_security_board import _entry, render_board  # noqa: E402


class SecurityBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import glob
        cls.paths = sorted(glob.glob(os.path.join(
            _ROOT, "results", "raw", "security_*.json")))
        if not cls.paths:
            raise unittest.SkipTest("no v1 security data present")
        cls.outdir = "/tmp/emox_secboard_test"
        import shutil
        shutil.rmtree(cls.outdir, ignore_errors=True)
        render_board(cls.paths, cls.outdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.outdir, ignore_errors=True)

    def test_entry_shape(self):
        e = _entry(self.paths[0])
        for key in ("model", "tests", "passed", "n", "rate",
                    "tokens", "secs", "scope"):
            self.assertIn(key, e)
        self.assertEqual(e["n"], len(e["tests"]))

    def test_files_written(self):
        self.assertTrue(os.path.isfile(
            os.path.join(self.outdir, "security-board.html")))
        self.assertTrue(os.path.isfile(
            os.path.join(self.outdir, "security-board.json")))

    def test_html_sections(self):
        page = open(os.path.join(self.outdir, "security-board.html"),
                    encoding="utf-8").read()
        for section in ("Rank table", "Per-test matrix", "<svg"):
            self.assertIn(section, page)
        self.assertNotIn("http://", page)

    def test_json_sorted_desc(self):
        data = json.load(open(os.path.join(self.outdir,
                                           "security-board.json"),
                              encoding="utf-8"))
        rates = [e["rate"] for e in data["entries"]]
        self.assertEqual(rates, sorted(rates, reverse=True))

    def test_detail_pages_linked(self):
        import glob as _glob
        pages = _glob.glob(os.path.join(self.outdir, "security_*.html"))
        self.assertGreaterEqual(len(pages), 2)
        board = open(os.path.join(self.outdir, "security-board.html"),
                     encoding="utf-8").read()
        self.assertIn(".html\">", board)  # rank/matrix link to details
        sample = open(pages[0], encoding="utf-8").read()
        for section in ("Run configuration", "Per-test detail",
                        "back to board"):
            self.assertIn(section, sample)
        # Config honesty: v1 files carry no model/temp/backend fields.
        self.assertIn("not recorded", sample)


if __name__ == "__main__":
    unittest.main()
