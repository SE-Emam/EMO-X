"""Composite/bootstrap/comparison/profile/registry: B54-B61, C65-C75, C81."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring
import metrics
import denominators


class TestComposite(unittest.TestCase):
    def test_geomean_renormalized_c73(self):
        dims = {"correctness": 0.9, "generalization": 0.8,
                "tool_discipline": None, "recovery": 0.7,
                "robustness": None, "efficiency": 0.6,
                "calibration": None, "long_horizon": 0.5}
        got = scoring.emo_capability_score(dims)
        import math
        w = scoring.DEFAULT_CAPABILITY_WEIGHTS
        defn = [(w[d], v) for d, v in dims.items() if v is not None]
        ws = sum(x for x, _ in defn)
        exp = 100 * math.exp(sum(x * math.log(v) for x, v in defn) / ws)
        self.assertAlmostEqual(got, exp)
        self.assertIsNone(scoring.emo_capability_score({}))

    def test_gate(self):
        dims = {d: 0.8 for d in scoring.DEFAULT_CAPABILITY_WEIGHTS}
        self.assertTrue(scoring.safety_eligibility_gate(0.0, 0.96, 0.85,
                                                        dims))
        self.assertFalse(scoring.safety_eligibility_gate(0.0, 0.90, 0.85,
                                                         dims))
        self.assertFalse(scoring.safety_eligibility_gate(0.0, 0.96, 0.70,
                                                         dims))
        self.assertFalse(scoring.safety_eligibility_gate(None, 0.96, 0.85,
                                                         dims))

    def test_overall_none_when_ineligible(self):
        dims = {d: 0.8 for d in scoring.DEFAULT_CAPABILITY_WEIGHTS}
        self.assertIsNone(scoring.emo_overall_score(dims, 0.05, 1.0, 1.0))
        self.assertIsNotNone(
            scoring.emo_overall_score(dims, 0.0, 1.0, 1.0))

    def test_bootstrap_ci_structure(self):
        groups = [[1.0, 1.0], [0.0, 0.0], [1.0, 0.0], [0.5]]
        out = scoring.bootstrap_ci(groups, B=200, seed=0)
        self.assertAlmostEqual(out["mean"], (1 + 0 + 0.5 + 0.5) / 4)
        self.assertLessEqual(out["ci_low"], out["mean"])
        self.assertGreaterEqual(out["ci_high"], out["mean"])
        self.assertTrue(out["low_sample"])  # C66: <10 families
        self.assertEqual(out["note"], "LOW-SAMPLE UNCERTAINTY")
        empty = scoring.bootstrap_ci([], B=10)
        self.assertIsNone(empty["mean"])

    def test_paired_diff(self):
        a = {"t1": [1.0], "t2": [0.5]}
        b = {"t1": [0.5], "t2": [0.5]}
        out = scoring.paired_bootstrap_diff(a, b, B=200, seed=1)
        self.assertAlmostEqual(out["mean"], 0.25)

    def test_b58_comparison_key(self):
        ka = scoring.make_comparison_key("p", "h", "m")
        kb = scoring.make_comparison_key("p", "h", "m")
        kc = scoring.make_comparison_key("p", "h", "X")
        self.assertTrue(scoring.directly_comparable(ka, kb))
        self.assertFalse(scoring.directly_comparable(ka, kc))


class TestProfile(unittest.TestCase):
    def test_assembly_eligible(self):
        dims = {d: 0.8 for d in scoring.DEFAULT_CAPABILITY_WEIGHTS}
        prof = metrics.assemble_capability_profile(
            dims, failure_fingerprint={"WRONG_TOOL": 0.1},
            efficiency={"tokens_per_solve": 100.0},
            ci_95=[70.0, 85.0], coverage=0.98,
            benchmark_health=0.85, safety=0.95, csv_rate=0.0)
        self.assertEqual(prof["eligibility"], "ELIGIBLE")
        self.assertIsNotNone(prof["EMO_Overall"])
        self.assertIn("capability_profile", prof)

    def test_assembly_ineligible_no_rank(self):
        dims = {d: 0.8 for d in scoring.DEFAULT_CAPABILITY_WEIGHTS}
        prof = metrics.assemble_capability_profile(
            dims, coverage=0.98, benchmark_health=0.85, csv_rate=0.05)
        self.assertEqual(prof["eligibility"], "NOT RANKABLE")
        self.assertIsNone(prof["EMO_Overall"])
        # dims still reportable (B56)
        self.assertAlmostEqual(
            prof["capability_profile"]["correctness"], 0.8)

    def test_required_fields_present(self):
        for f in ("pass_rate", "partial_credit", "generalization",
                  "tool_discipline", "recovery_rate", "efficiency",
                  "calibration", "safety", "long_horizon",
                  "human_minutes_solved", "failure_fingerprint",
                  "ci_95", "coverage", "benchmark_health"):
            self.assertIn(f, metrics.REQUIRED_PROFILE_FIELDS)


class TestRegistry(unittest.TestCase):
    def test_every_entry_has_six_answers_c93(self):
        for name, entry in denominators.METRIC_REGISTRY.items():
            for key in ("unit", "eligible", "numerator", "denominator",
                        "exclusions", "d_zero"):
                self.assertIn(key, entry, "%s missing %s" % (name, key))

    def test_eligible_attempts_c9(self):
        events = [
            {"primary_status": "PASS"},
            {"primary_status": "VOID"},
            {"primary_status": "ERROR"},
            {"primary_status": "FAIL",
             "eligible_for_pass_rate": False},
            {"primary_status": "FAIL"},
        ]
        self.assertEqual(len(denominators.eligible_attempts(events)), 3)
        self.assertEqual(
            len(denominators.eligible_attempts(events, "pass_rate")), 2)
        # missing flag defaults True
        self.assertEqual(
            len(denominators.eligible_attempts(
                [{"primary_status": "PASS"}], "calibration")), 1)


if __name__ == "__main__":
    unittest.main()
