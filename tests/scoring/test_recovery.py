"""Recovery: B23-B27 / C28-C32."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


def ep(recovered, **kw):
    d = {
        "recoverable": True,
        "injection_succeeded": True,
        "infra_valid": True,
        "recovered": recovered,
    }
    d.update(kw)
    return d


class TestRecovery(unittest.TestCase):
    def test_basic_rate(self):
        eps = [ep(True), ep(False), ep(True)]
        self.assertAlmostEqual(scoring.recovery_rate(eps), 2 / 3)

    def test_non_recoverable_excluded_c30(self):
        eps = [ep(False), ep(False, recoverable=False)]
        self.assertAlmostEqual(scoring.recovery_rate(eps), 0.0)

    def test_failed_injection_and_infra_excluded_c29(self):
        eps = [ep(False, injection_succeeded=False), ep(False, infra_valid=False)]
        self.assertIsNone(scoring.recovery_rate(eps))

    def test_no_fault_is_na(self):
        self.assertIsNone(scoring.recovery_rate([]))

    def test_weighted(self):
        eps = [ep(True, weight=3.0), ep(False, weight=1.0)]
        self.assertAlmostEqual(scoring.recovery_rate(eps), 0.75)

    def test_rae(self):
        self.assertAlmostEqual(scoring.recovery_action_efficiency(8, 5), 5 / 8)
        self.assertAlmostEqual(scoring.recovery_action_efficiency(3, 5), 1.0)
        self.assertIsNone(scoring.recovery_action_efficiency(3, None))

    def test_rle(self):
        self.assertAlmostEqual(scoring.recovery_latency_efficiency(10.0, 5.0), 0.5)

    def test_verification_after_recovery(self):
        self.assertAlmostEqual(scoring.verification_after_recovery(2, 4), 0.5)
        self.assertIsNone(scoring.verification_after_recovery(0, 0))

    def test_recovery_score_geomean(self):
        self.assertAlmostEqual(scoring.recovery_score([0.5, 1.0]), (0.5) ** 0.5)
        self.assertIsNone(scoring.recovery_score([]))


if __name__ == "__main__":
    unittest.main()
