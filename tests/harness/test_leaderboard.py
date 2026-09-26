"""Tests for render_leaderboard.py (1..N runs, bands, no false ranks)."""

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

from render_leaderboard import rank_band, render_board  # noqa: E402
from runner import run_suite, stub_chat_factory  # noqa: E402


def _stub_run(root, families, seed=1):
    rundir, _ = run_suite(
        "dynamic-code", stub_chat_factory("board-test"), "m", "stub",
        seed=seed, instances=1, trials=1, fault_rate=0.0,
        out_root=os.path.join(root, "raw"), families=families)
    return rundir


class RankBandTests(unittest.TestCase):
    def test_overlapping_cis_share_band(self):
        entries = [
            {"model": "a", "pass_rate": 0.9, "ci_low": 0.7, "ci_high": 1.0},
            {"model": "b", "pass_rate": 0.8, "ci_low": 0.6, "ci_high": 0.95},
        ]
        out = rank_band(entries)
        self.assertEqual([e["band"] for e in out], [0, 0])

    def test_disjoint_ci_new_band(self):
        entries = [
            {"model": "a", "pass_rate": 0.9, "ci_low": 0.8, "ci_high": 1.0},
            {"model": "b", "pass_rate": 0.2, "ci_low": 0.0, "ci_high": 0.3},
        ]
        out = rank_band(entries)
        self.assertEqual([e["band"] for e in out], [0, 1])

    def test_na_ci_stays_band_zero(self):
        entries = [{"model": "a", "pass_rate": None,
                    "ci_low": None, "ci_high": None}]
        out = rank_band(entries)
        self.assertEqual(out[0]["band"], 0)


class LeaderboardRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = "/tmp/emox_board_test"
        shutil.rmtree(cls.root, ignore_errors=True)
        cls.dir_a = _stub_run(cls.root, ["DC1"], seed=1)
        cls.dir_b = _stub_run(cls.root, ["DC2"], seed=2)
        cls.outdir = os.path.join(cls.root, "board")
        render_board([cls.dir_a, cls.dir_b], cls.outdir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_files_written(self):
        self.assertTrue(os.path.isfile(
            os.path.join(self.outdir, "leaderboard.html")))
        self.assertTrue(os.path.isfile(
            os.path.join(self.outdir, "leaderboard.json")))

    def test_single_run_also_works(self):
        single = os.path.join(self.root, "single")
        render_board([self.dir_a], single)
        page = open(os.path.join(single, "leaderboard.html"),
                    encoding="utf-8").read()
        self.assertIn("1 run", page)

    def test_html_sections(self):
        page = open(os.path.join(self.outdir, "leaderboard.html"),
                    encoding="utf-8").read()
        for section in ("Rank table", "Pairwise calls", "<svg"):
            self.assertIn(section, page)
        self.assertNotIn("winner declared", page.lower())
        self.assertNotIn("beats ", page.lower())
        self.assertNotIn("http://", page)

    def test_json_pairwise(self):
        data = json.load(open(os.path.join(self.outdir, "leaderboard.json"),
                              encoding="utf-8"))
        self.assertEqual(len(data["entries"]), 2)
        self.assertEqual(len(data["pairwise"]), 1)
        self.assertIn(data["pairwise"][0]["status"],
                      ("significant", "directional", "inconclusive",
                       "non-comparable", "insufficient-data"))


if __name__ == "__main__":
    unittest.main()
