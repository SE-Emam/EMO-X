"""Paired model-comparison statistics: B54 duels, no fixed gap rule (Y-6).

Acceptance: 24/25 vs 23/25 lands directional/inconclusive, never
significant; mismatched manifests give non-comparable; a large gap is
significant; render output carries Difference/Status lines with
ranking-free language; paired_bootstrap_diff(..., return_reps=True)
replicates are deterministic and match the bootstrap_ci scheme.
"""

import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring
import report_v2

BAD_WORDS = ("win", "beats", "winner")


def _attempt(family, passed, score=None):
    if score is None:
        score = 1.0 if passed else 0.0
    return {"task_family_id": family, "variant_class": "std",
            "instance_id": family + "-0",
            "primary_status": "PASS" if passed else "FAIL",
            "score": float(score)}


def _close_call_attempts():
    """25 shared families: A passes 24, B passes 23 (one-family gap)."""
    fams = ["fam%02d" % i for i in range(25)]
    att_a = [_attempt(f, i < 24) for i, f in enumerate(fams)]
    att_b = [_attempt(f, i < 23) for i, f in enumerate(fams)]
    return att_a, att_b


def _matching_manifests():
    key = {"prompt_sha256": "p", "harness_sha256": "h",
           "manifest_sha256": "m"}
    return ({"comparison_key": dict(key), "backend_capabilities": {}},
            {"comparison_key": dict(key), "backend_capabilities": {}})


def _mismatched_manifests():
    man_a = {"comparison_key": {"prompt_sha256": "p",
                                "harness_sha256": "h",
                                "manifest_sha256": "m"},
             "backend_capabilities": {}}
    man_b = {"comparison_key": {"prompt_sha256": "p",
                                "harness_sha256": "h",
                                "manifest_sha256": "OTHER"},
             "backend_capabilities": {}}
    return man_a, man_b


def _assert_ranking_free(testcase, text):
    lowered = text.lower()
    for bad in BAD_WORDS:
        testcase.assertNotIn(bad, lowered,
                             "ranking language %r in render" % bad)


class TestReturnReps(unittest.TestCase):
    def test_default_omits_reps(self):
        out = scoring.paired_bootstrap_diff({"t1": [1.0], "t2": [0.5]},
                                            {"t1": [0.5], "t2": [0.5]},
                                            B=50, seed=3)
        self.assertNotIn("reps", out)

    def test_reps_deterministic_and_match_bootstrap_scheme(self):
        groups_a = {"t1": [1.0, 0.0], "t2": [0.5], "t3": [1.0]}
        groups_b = {"t1": [0.5, 0.5], "t2": [0.0], "t3": [0.0]}
        first = scoring.paired_bootstrap_diff(
            groups_a, groups_b, B=200, seed=7, return_reps=True)
        second = scoring.paired_bootstrap_diff(
            groups_a, groups_b, B=200, seed=7, return_reps=True)
        self.assertIn("reps", first)
        self.assertEqual(len(first["reps"]), 200)
        self.assertEqual(first["reps"], second["reps"])
        # Independent recomputation with the same seed/scheme as
        # bootstrap_ci internals (resample whole families, mean of
        # family means).
        keys = [k for k in groups_a if k in groups_b]
        diffs = []
        for k in keys:
            ga = [v for v in groups_a[k] if v is not None]
            gb = [v for v in groups_b[k] if v is not None]
            diffs.append(sum(ga) / len(ga) - sum(gb) / len(gb))
        fam = [[d] for d in diffs]
        rng = random.Random(7)
        expected = []
        for _ in range(200):
            sample = [fam[rng.randrange(len(fam))]
                      for _ in range(len(fam))]
            vals = [g[0] for g in sample]
            expected.append(sum(vals) / len(vals))
        self.assertEqual(first["reps"], expected)
        # Point and interval match bootstrap_ci on the same families.
        direct = scoring.bootstrap_ci(fam, B=200, seed=7)
        self.assertAlmostEqual(first["mean"], direct["mean"])
        self.assertAlmostEqual(first["ci_low"], direct["ci_low"])
        self.assertAlmostEqual(first["ci_high"], direct["ci_high"])

    def test_empty_reps_on_no_overlap(self):
        out = scoring.paired_bootstrap_diff({"a": [1.0]}, {"b": [1.0]},
                                            B=50, seed=0,
                                            return_reps=True)
        self.assertIsNone(out["mean"])
        self.assertEqual(out["reps"], [])


class TestCompareModels(unittest.TestCase):
    def test_close_call_never_significant(self):
        att_a, att_b = _close_call_attempts()
        man_a, man_b = _matching_manifests()
        for seed in (0, 1, 2):
            comp = report_v2.compare_models(
                att_a, att_b, "model-a", "model-b",
                manifest_a=man_a, manifest_b=man_b, B=2000, seed=seed)
            self.assertIn(comp["status"], ("directional", "inconclusive"),
                          "seed %d gave %s" % (seed, comp["status"]))
            self.assertNotEqual(comp["status"], "significant")
            self.assertAlmostEqual(comp["paired_difference"], 0.04)
            self.assertAlmostEqual(comp["pass_rate_a"], 24 / 25)
            self.assertAlmostEqual(comp["pass_rate_b"], 23 / 25)
            for key in ("ci_a", "ci_b"):
                for field in ("ci_low", "ci_high", "se"):
                    self.assertIsNotNone(comp[key][field])

    def test_leg_cis_use_one_bootstrap_stream(self):
        """ci_a and ci_b must come from the SAME resampling stream, and
        must equal what the per-run report prints for the same leg.

        An offset seed (seed+1) for leg B made the comparison's interval
        disagree with the leaderboard's uncertainty_95 for the identical
        leg by pure resampling noise: two surfaces, two numbers.

        The legs here are deliberately high-variance (3 trials/family,
        mixed outcomes) so the assertion actually discriminates seeds --
        a near-degenerate leg makes the test pass either way.
        """
        def _noisy(offset):
            out = []
            for i in range(25):
                for t in range(1, 4):
                    ok = (i * 7 + t * 3 + offset) % 5 != 0
                    out.append({
                        "run_id": "leg", "model_id": "m",
                        "task_family_id": "fam%02d" % i,
                        "instance_id": "fam%02d" % i,
                        "variant_class": "canonical", "trial_id": t,
                        "primary_status": "PASS" if ok else "FAIL",
                        "primary_failure": None if ok else "ASSERTION_FAILED",
                        "score": 1.0 if ok else 0.0,
                    })
            return out

        att_a, att_b = _noisy(0), _noisy(1)
        man_a, man_b = _matching_manifests()

        # Contract check by spy: both per-leg intervals must be drawn from
        # ONE resampling stream. Percentile equality cannot prove this --
        # the bootstrap stat is lattice-valued, so two seeds routinely
        # return bit-identical endpoints and a numeric test passes either
        # way (verified: a numeric version of this test was vacuous).
        seeds = []
        real_ci = scoring.bootstrap_ci

        def spy(groups, stat=None, B=scoring.BOOTSTRAP_RESAMPLES, seed=0):
            seeds.append(seed)
            return real_ci(groups, stat=stat, B=B, seed=seed)

        scoring.bootstrap_ci = spy
        try:
            comp = report_v2.compare_models(
                att_a, att_b, "model-a", "model-b",
                manifest_a=man_a, manifest_b=man_b, B=2000, seed=0)
        finally:
            scoring.bootstrap_ci = real_ci
        self.assertGreaterEqual(len(seeds), 2)
        self.assertEqual(set(seeds), {0},
                         "all bootstrap intervals in one comparison must "
                         "share one stream; got seeds %r" % (seeds,))

        # Cross-surface agreement: comparison CI == per-run report CI.
        for attempts, key in ((att_a, "ci_a"), (att_b, "ci_b")):
            unc = report_v2.build_v2_report(attempts, [], model_id="m")["uncertainty_95"]
            self.assertAlmostEqual(comp[key]["ci_low"], unc["low"], places=12)
            self.assertAlmostEqual(comp[key]["ci_high"], unc["high"], places=12)

    def test_mismatched_manifests_non_comparable(self):
        att_a, att_b = _close_call_attempts()
        man_a, man_b = _mismatched_manifests()
        comp = report_v2.compare_models(
            att_a, att_b, "model-a", "model-b",
            manifest_a=man_a, manifest_b=man_b, B=200, seed=0)
        self.assertEqual(comp["comparability"], "NON_COMPARABLE")
        self.assertEqual(comp["status"], "non-comparable")
        self.assertNotIn("paired_difference", comp)
        text = report_v2.render_comparison(comp)
        self.assertIn("Status", text)
        self.assertIn("non-comparable", text)
        self.assertNotIn("Difference", text)
        _assert_ranking_free(self, text)

    def test_large_gap_significant(self):
        fams = ["fam%02d" % i for i in range(25)]
        att_a = [_attempt(f, True) for f in fams]
        att_b = [_attempt(f, False) for f in fams]
        man_a, man_b = _matching_manifests()
        comp = report_v2.compare_models(
            att_a, att_b, "model-a", "model-b",
            manifest_a=man_a, manifest_b=man_b, B=500, seed=0)
        self.assertEqual(comp["status"], "significant")
        self.assertAlmostEqual(comp["paired_difference"], 1.0)
        low, high = comp["difference_ci"]
        self.assertGreater(low, 0)
        text = report_v2.render_comparison(comp)
        self.assertIn("Difference", text)
        self.assertIn("Status", text)
        self.assertIn("significant", text)
        _assert_ranking_free(self, text)

    def test_directional_lean(self):
        fams = ["fam%02d" % i for i in range(20)]
        att_a = ([_attempt(f, False, score=0.3) for f in fams[:18]]
                 + [_attempt(f, False, score=0.0) for f in fams[18:]])
        att_b = ([_attempt(f, False, score=0.0) for f in fams[:18]]
                 + [_attempt(f, True, score=1.0) for f in fams[18:]])
        man_a, man_b = _matching_manifests()
        comp = report_v2.compare_models(
            att_a, att_b, "model-a", "model-b",
            manifest_a=man_a, manifest_b=man_b, B=4000, seed=0)
        self.assertEqual(comp["status"], "directional")
        low, high = comp["difference_ci"]
        self.assertLessEqual(low, 0)
        self.assertGreaterEqual(comp["sign_consistency"], 0.90)
        text = report_v2.render_comparison(comp)
        self.assertIn("Difference", text)
        self.assertIn("Status", text)
        _assert_ranking_free(self, text)

    def test_insufficient_data_without_overlap(self):
        att_a = [_attempt("a%02d" % i, True) for i in range(5)]
        att_b = [_attempt("b%02d" % i, True) for i in range(5)]
        man_a, man_b = _matching_manifests()
        comp = report_v2.compare_models(
            att_a, att_b, "model-a", "model-b",
            manifest_a=man_a, manifest_b=man_b, B=200, seed=0)
        self.assertEqual(comp["status"], "insufficient-data")

    def test_close_call_render_language(self):
        att_a, att_b = _close_call_attempts()
        man_a, man_b = _matching_manifests()
        comp = report_v2.compare_models(
            att_a, att_b, "model-a", "model-b",
            manifest_a=man_a, manifest_b=man_b, B=500, seed=0)
        text = report_v2.render_comparison(comp)
        self.assertIn("Difference", text)
        self.assertIn("Status", text)
        _assert_ranking_free(self, text)


def _inst_attempt(family, inst, passed):
    rec = _attempt(family, passed)
    rec["instance_id"] = inst
    rec["trial_id"] = 1
    return rec


class NumericGuardTests(unittest.TestCase):
    def test_antisymmetric_pairing(self):
        ga = {"t1": [1.0, 1.0, 0.0], "t2": [0.5]}
        gb = {"t1": [0.0, 1.0, 0.0], "t2": [0.5]}
        fwd = scoring.paired_bootstrap_diff(ga, gb, B=2000, seed=7)
        rev = scoring.paired_bootstrap_diff(gb, ga, B=2000, seed=7)
        self.assertAlmostEqual(fwd["mean"], -rev["mean"])
        self.assertAlmostEqual(fwd["ci_low"], -rev["ci_high"])
        self.assertAlmostEqual(fwd["ci_high"], -rev["ci_low"])

    def test_bootstrap_b_bounds(self):
        for bad in (0, -5, True, "100"):
            with self.assertRaises(ValueError):
                scoring.bootstrap_ci([[1.0]], B=bad)
        with self.assertRaises(ValueError):
            scoring.bootstrap_ci([[1.0]], B=scoring.BOOTSTRAP_MAX + 1)
        out = scoring.bootstrap_ci([[1.0, 0.0]], B=200, seed=1)
        self.assertEqual(out["B"], 200)


class InstancePairingTests(unittest.TestCase):
    def test_shared_instances_pair_at_instance_level(self):
        att_a = [_inst_attempt("t1", "t1-0", True),
                 _inst_attempt("t1", "t1-1", False),
                 _inst_attempt("t2", "t2-0", True)]
        att_b = [_inst_attempt("t1", "t1-0", False),
                 _inst_attempt("t1", "t1-1", False),
                 _inst_attempt("t2", "t2-0", True)]
        out = scoring.instance_paired_bootstrap(att_a, att_b, B=500,
                                                seed=0)
        self.assertEqual(out["level"], "instance")
        self.assertEqual(out["n_paired"], 3)
        # diffs: +1, 0, 0 -> mean 1/3
        self.assertAlmostEqual(out["mean"], 1 / 3, places=2)

    def test_no_shared_instances_falls_back_with_flag(self):
        att_a = [_inst_attempt("t1", "a-0", True)]
        att_b = [_inst_attempt("t1", "b-0", False)]
        out = scoring.instance_paired_bootstrap(att_a, att_b, B=500,
                                                seed=0)
        self.assertEqual(out["level"], "family-fallback")
        self.assertIsNotNone(out["mean"])

    def test_canonical_group_builders(self):
        events = [_inst_attempt("t1", "t1-0", True),
                  _inst_attempt("t1", "t1-1", False)]
        strict = scoring.family_strict_lists(events)
        self.assertEqual(sorted(strict["t1"]), [0, 1])
        means = scoring.instance_mean_scores(events)
        self.assertEqual(means[("t1", "t1-0")], 1.0)

    def test_compare_reports_pairing_level(self):
        man_a, man_b = _matching_manifests()
        att_a = [_inst_attempt("t1", "t1-0", True)]
        att_b = [_inst_attempt("t1", "t1-0", True)]
        comp = report_v2.compare_models(
            att_a, att_b, "model-a", "model-b",
            manifest_a=man_a, manifest_b=man_b, B=500, seed=0)
        self.assertEqual(comp.get("pairing_level"), "instance")


if __name__ == "__main__":
    unittest.main()
