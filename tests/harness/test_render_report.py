"""Tests for render_report.py (local HTML report, no network/deps)."""

import json
import os
import shutil
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from render_report import render  # noqa: E402
from runner import run_suite, stub_chat_factory  # noqa: E402


class RenderReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = "/tmp/emox_render_test"
        shutil.rmtree(cls.root, ignore_errors=True)
        rundir, _ = run_suite(
            "dynamic-code",
            stub_chat_factory("render-test"),
            "m",
            "stub",
            seed=1,
            instances=1,
            trials=1,
            fault_rate=0.0,
            out_root=os.path.join(cls.root, "raw"),
            families=["DC1"],
        )
        cls.rundir = rundir
        cls.outdir = os.path.join(cls.root, "rep")
        render(cls.rundir, cls.outdir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_files_written(self):
        self.assertTrue(os.path.isfile(os.path.join(self.outdir, "report.html")))
        self.assertTrue(os.path.isfile(os.path.join(self.outdir, "report.json")))

    def test_html_sections(self):
        page = open(os.path.join(self.outdir, "report.html"), encoding="utf-8").read()
        for section in (
            "Capability profile",
            "Failure fingerprint",
            "Efficiency",
            "Uncertainty",
            "Run conditions",
        ):
            self.assertIn(section, page)
        self.assertIn("<svg", page)  # inline bars, no external assets
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)

    def test_json_roundtrip(self):
        data = json.load(open(os.path.join(self.outdir, "report.json"), encoding="utf-8"))
        self.assertIn("manifest", data)
        self.assertIn("report", data)
        self.assertEqual(data["manifest"]["suite"], "dynamic-code")


if __name__ == "__main__":
    unittest.main()
