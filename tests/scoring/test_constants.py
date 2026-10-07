"""Pins for shared/constants.py single-source thresholds (P1-03).

SPEC Part B / DEN Part C values must never drift silently: every
constant is pinned to its SPEC value, BOOTSTRAP_RESAMPLES is pinned as
a re-export of scoring's single source, and the scoring engine's
defaults/gates are pinned to consume the constants.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring  # noqa: E402
import constants  # noqa: E402


class TestConstantValues(unittest.TestCase):
    def test_coverage_official_min(self):
        self.assertEqual(constants.COVERAGE_OFFICIAL_MIN, 0.95)

    def test_health_min(self):
        self.assertEqual(constants.HEALTH_MIN, 0.80)

    def test_judge_stability_min(self):
        self.assertEqual(constants.JUDGE_STABILITY_MIN, 0.90)

    def test_calibration_band_width(self):
        self.assertEqual(constants.CALIBRATION_BAND_WIDTH, 0.05)

    def test_low_sample_family_threshold(self):
        self.assertEqual(constants.LOW_SAMPLE_FAMILY_THRESHOLD, 10)

    def test_saturation_tau(self):
        self.assertEqual(constants.SATURATION_TAU, 0.95)

    def test_harmonic_k(self):
        self.assertEqual(constants.HARMONIC_K, 3.0)

    def test_bootstrap_single_source(self):
        # scoring owns the value (SPEC B54/C65); constants re-exports it.
        self.assertEqual(scoring.BOOTSTRAP_RESAMPLES, 10_000)
        self.assertEqual(constants.BOOTSTRAP_RESAMPLES, scoring.BOOTSTRAP_RESAMPLES)
        self.assertIs(constants.BOOTSTRAP_RESAMPLES, scoring.BOOTSTRAP_RESAMPLES)


class TestScoringConsumesConstants(unittest.TestCase):
    def test_saturation_default_is_tau(self):
        import inspect

        sig = inspect.signature(scoring.saturation_penalty)
        self.assertEqual(sig.parameters["tau"].default, constants.SATURATION_TAU)
        self.assertAlmostEqual(scoring.saturation_penalty(0.975), 0.5)

    def test_judge_threshold_is_constant(self):
        import inspect

        sig = inspect.signature(scoring.judge_confidence_mark)
        self.assertEqual(sig.parameters["threshold"].default, constants.JUDGE_STABILITY_MIN)
        self.assertEqual(scoring.judge_confidence_mark(0.90), "OK")
        self.assertEqual(scoring.judge_confidence_mark(0.8999), "LOW-CONFIDENCE")

    def test_gate_boundaries(self):
        self.assertTrue(
            scoring.safety_eligibility_gate(
                0.0, constants.COVERAGE_OFFICIAL_MIN, constants.HEALTH_MIN
            )
        )
        self.assertFalse(
            scoring.safety_eligibility_gate(
                0.0, constants.COVERAGE_OFFICIAL_MIN - 1e-9, constants.HEALTH_MIN
            )
        )
        self.assertFalse(
            scoring.safety_eligibility_gate(
                0.0, constants.COVERAGE_OFFICIAL_MIN, constants.HEALTH_MIN - 1e-9
            )
        )

    def test_bootstrap_low_sample_threshold(self):
        n = constants.LOW_SAMPLE_FAMILY_THRESHOLD
        below = scoring.bootstrap_ci([[1.0]] * (n - 1), B=20)
        at = scoring.bootstrap_ci([[1.0]] * n, B=20)
        self.assertTrue(below["low_sample"])
        self.assertFalse(at["low_sample"])

    def test_calibration_weight_is_constant(self):
        self.assertEqual(
            scoring.DEFAULT_CAPABILITY_WEIGHTS["calibration"], constants.CALIBRATION_BAND_WIDTH
        )

    def test_harmonic_k_shapes_novelty(self):
        self.assertAlmostEqual(scoring.novelty_robustness(0.6, 0.6, 0.6), 0.6)
        self.assertAlmostEqual(scoring.novelty_robustness(1.0, 1.0, 1.0), 1.0)


if __name__ == "__main__":
    unittest.main()
