"""Tests for render_health_board.py + health wiring (review P2)."""

import json
import os
import shutil
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
for _p in (ROOT, SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import runner  # noqa: E402
import render_health_board as hb  # noqa: E402


def _attempt(family, variant, passed, trial=1, model="m"):
    return {
        "run_id": "r",
        "model_id": model,
        "task_family_id": family,
        "instance_id": "%s-1" % family,
        "variant_class": variant,
        "trial_id": trial,
        "primary_status": "PASS" if passed else "FAIL",
        "score": 1.0 if passed else 0.0,
    }


def _write_run(root, run_id, attempts):
    d = os.path.join(root, run_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "events.jsonl"), "w") as f:
        for a in attempts:
            f.write(json.dumps(a) + "\n")
    return d


class HealthWiringTests(unittest.TestCase):
    def test_contamination_pairs_from_variants(self):
        root = "/tmp/emox_hw_test"
        shutil.rmtree(root, ignore_errors=True)
        attempts = []
        for i in range(1, 5):
            attempts.append(_attempt("T1", "canonical", True, trial=i))
        for i in range(1, 5):
            attempts.append(_attempt("T1", "novel", i <= 1, trial=i))
        _write_run(root, "RUN-1", attempts)
        snap = runner.health_snapshot(root)
        self.assertEqual(len(snap["contamination_by_task"]), 1)
        level = snap["contamination_by_task"]["T1"]["level"]
        self.assertIn(level, ("low", "elevated", "high"))
        self.assertEqual(snap["contamination"]["retention"], 0.25)

    def test_no_novel_variants_is_unknown_not_zero(self):
        root = "/tmp/emox_hw_test2"
        shutil.rmtree(root, ignore_errors=True)
        _write_run(root, "RUN-1", [_attempt("T1", "canonical", True, trial=i) for i in range(1, 4)])
        snap = runner.health_snapshot(root)
        self.assertEqual(snap["contamination"]["level"], "unknown")
        self.assertIsNone(snap["contamination"]["risk"])
        self.assertEqual(snap["rotation_candidates"], [])

    def test_saturation_per_task_needs_refs(self):
        root = "/tmp/emox_hw_test3"
        shutil.rmtree(root, ignore_errors=True)
        attempts = []
        for m in ("a", "b"):
            attempts += [_attempt("T1", "canonical", True, trial=i, model=m) for i in range(1, 3)]
        _write_run(root, "RUN-1", attempts)
        snap = runner.health_snapshot(root)
        self.assertEqual(snap["saturation"]["T1"]["n_ref"], 2)
        self.assertFalse(snap["saturation"]["T1"]["saturated"])


class HealthBoardTests(unittest.TestCase):
    def test_board_renders(self):
        root = "/tmp/emox_hw_test4"
        shutil.rmtree(root, ignore_errors=True)
        _write_run(root, "RUN-1", [_attempt("T1", "canonical", True, trial=i) for i in range(1, 3)])
        outdir = "/tmp/emox_hb_test"
        shutil.rmtree(outdir, ignore_errors=True)
        path = hb.render_board(root, outdir)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.path.isfile(os.path.join(outdir, "health-board.json")))
        page = open(path, encoding="utf-8").read()
        self.assertIn("Health board", page)
        self.assertIn("T1", page)


if __name__ == "__main__":
    unittest.main()
