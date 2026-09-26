"""Tests for Novelty Robustness (skill-vs-memory separator) + HM-lite wiring."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scoring  # noqa: E402


class NoveltyRobustnessTests(unittest.TestCase):
    def test_memorizer_scores_low(self):
        # Canonical 100%, perturbed 90%, novel collapses: NOT robust.
        nr = scoring.novelty_robustness(1.0, 0.90, 0.20)
        self.assertLess(nr, 0.50)

    def test_robust_model_scores_high(self):
        # The user's headline example: 96 / 92 / 94.
        nr = scoring.novelty_robustness(0.96, 0.92, 0.94)
        self.assertGreater(nr, 0.90)
        self.assertLessEqual(nr, 0.96)  # harmonic never exceeds levels

    def test_na_propagates(self):
        self.assertIsNone(scoring.novelty_robustness(0.9, 0.9, None))
        self.assertIsNone(scoring.novelty_robustness(None, 0.9, 0.9))

    def test_benchmark_mean_over_eligible(self):
        val = scoring.novelty_robustness_benchmark(
            [(1.0, 0.9, 0.2), (0.96, 0.92, 0.94), (None, 0.5, 0.5)])
        lo = scoring.novelty_robustness(1.0, 0.9, 0.2)
        hi = scoring.novelty_robustness(0.96, 0.92, 0.94)
        self.assertAlmostEqual(val, (lo + hi) / 2)
        self.assertIsNone(scoring.novelty_robustness_benchmark([]))


class HumanMinutesWiringTests(unittest.TestCase):
    def test_manifests_carry_estimates(self):
        import json
        checked = 0
        for root, _, files in os.walk(os.path.join(_ROOT, "suites")):
            for f in files:
                if not f.endswith(".json"):
                    continue
                m = json.load(open(os.path.join(root, f)))
                self.assertIn("estimated_human_minutes", m, f)
                self.assertGreater(m["estimated_human_minutes"], 0)
                checked += 1
        self.assertGreater(checked, 50)

    def test_runner_enriches_responses(self):
        import runner
        from runner import stub_chat_factory
        out = os.path.join(_ROOT, "results", "raw")
        _, summary = runner.run_suite(
            "dynamic-code", stub_chat_factory("hm-test"), "m", "stub",
            seed=1, instances=1, trials=1, fault_rate=0.0,
            out_root=out, families=["DC1"])
        import json as _json
        rundir = summary["run_dir"]
        try:
            events = [_json.loads(l) for l in
                      open(os.path.join(rundir, "events.jsonl"))
                      if l.strip()]
            resps = [_json.loads(l) for l in
                     open(os.path.join(rundir, "responses.jsonl"))
                     if l.strip()]
            self.assertTrue(events)
            self.assertTrue(all(
                r.get("human_minutes") == 8 for r in resps))
            hm = [t for t in resps if t.get("human_minutes") is not None]
            rate = scoring.human_minutes_rate(
                [{"human_minutes": r["human_minutes"], "score": 0.0}
                 for r in hm])
            self.assertEqual(rate, 0.0)  # stub always FAILs: 0 minutes earned
        finally:
            import shutil
            shutil.rmtree(rundir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
