"""Golden formula values: one hand-checked number per formula family.

SPEC Part B goldens cross-checked against DEN Part C denominators.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring

GOLDENS = {
    # B4: 0.25*1 + 0.5*1 + 0.25*0
    "task_score": 0.75,
    # B9: 4*0.5*0.5
    "instability_p50": 1.0,
    # B10: 1 - C(2,2)/C(5,2)
    "pass_at_k_5_3_2": 0.9,
    # B11: C(3,2)/C(5,2)
    "consistency_5_3_2": 0.3,
    # C47 arithmetic default over [0.96, 0.93, 0.91]
    "generalization_arith": (0.96 + 0.93 + 0.91) / 3,
    # B13: 0.96 - 0.91
    "novelty_gap": 0.05,
    # B14: min(1, 0.91/0.96)
    "novelty_retention": 0.91 / 0.96,
    # B17: P=0.5 R=1.0
    "tool_f1": 2 * 0.5 * 1.0 / 1.5,
    # B20: 8/13
    "uar": 8 / 13,
    # B23: 2/3
    "recovery_rate": 2 / 3,
    # B32: ((0.8-1)^2 + (0.2-0)^2)/2
    "brier": 0.04,
    # B36: (0.8+0.9)/2
    "bra": 0.85,
    # B38/B56 gate value
    "csv_clean": 0.0,
    # B44: 7/10
    "step_survival": 0.7,
    # B47 absolute
    "scaffold_gain_abs": 0.2,
    # B48: 4*0.5*0.5
    "flakiness": 1.0,
    # B49: (0.975-0.95)/0.05
    "saturation_half": 0.5,
    # B51: 1 - 1/100
    "validity": 0.99,
}


class TestGoldenFormulas(unittest.TestCase):
    def test_task_score(self):
        s, _ = scoring.score_task([1, 1, 0], [0.25, 0.50, 0.25])
        self.assertAlmostEqual(s, GOLDENS["task_score"])

    def test_instability(self):
        self.assertAlmostEqual(scoring.instability_from_p(0.5), GOLDENS["instability_p50"])

    def test_at_k(self):
        self.assertAlmostEqual(scoring.pass_at_k(5, 3, 2), GOLDENS["pass_at_k_5_3_2"])
        self.assertAlmostEqual(scoring.consistency_at_k(5, 3, 2), GOLDENS["consistency_5_3_2"])

    def test_generalization(self):
        self.assertAlmostEqual(
            scoring.generalization_score([0.96, 0.93, 0.91]), GOLDENS["generalization_arith"]
        )

    def test_novelty(self):
        self.assertAlmostEqual(scoring.novelty_gap(0.96, 0.91), GOLDENS["novelty_gap"])
        self.assertAlmostEqual(scoring.novelty_retention(0.96, 0.91), GOLDENS["novelty_retention"])

    def test_tool(self):
        self.assertAlmostEqual(scoring.tool_f1(0.5, 1.0, True), GOLDENS["tool_f1"])
        self.assertAlmostEqual(scoring.unnecessary_action_rate(8, 13), GOLDENS["uar"])

    def test_recovery(self):
        eps = [
            {"recoverable": True, "injection_succeeded": True, "infra_valid": True, "recovered": r}
            for r in (True, True, False)
        ]
        self.assertAlmostEqual(scoring.recovery_rate(eps), GOLDENS["recovery_rate"])

    def test_brier(self):
        cases = [{"confidence": 0.8, "outcome": 1}, {"confidence": 0.2, "outcome": 0}]
        self.assertAlmostEqual(scoring.brier_score(cases), GOLDENS["brier"])

    def test_bra(self):
        self.assertAlmostEqual(scoring.balanced_refusal_accuracy(0.8, 0.9), GOLDENS["bra"])

    def test_csv(self):
        self.assertAlmostEqual(scoring.csv_rate(0, 25), GOLDENS["csv_clean"])

    def test_survival(self):
        self.assertAlmostEqual(scoring.step_survival(7, 10), GOLDENS["step_survival"])

    def test_scaffold(self):
        self.assertAlmostEqual(
            scoring.scaffold_gain(0.5, 0.7)["absolute"], GOLDENS["scaffold_gain_abs"]
        )

    def test_health(self):
        self.assertAlmostEqual(scoring.flakiness(0.5), GOLDENS["flakiness"])
        self.assertAlmostEqual(scoring.saturation_penalty(0.975), GOLDENS["saturation_half"])
        self.assertAlmostEqual(scoring.harness_validity(1, 100), GOLDENS["validity"])

    def test_golden_table_complete(self):
        self.assertGreaterEqual(len(GOLDENS), 14)


if __name__ == "__main__":
    unittest.main()
