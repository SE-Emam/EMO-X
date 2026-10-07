"""Efficiency: B28-B29 / C42-C45."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


def ev(status, score, tokens=0, cost=None, **kw):
    d = {
        "run_id": "R",
        "model_id": "M",
        "task_family_id": "T",
        "instance_id": "i",
        "variant_class": "canonical",
        "trial_id": 1,
        "primary_status": status,
        "score": score,
        "tokens": tokens,
    }
    if cost is not None:
        d["cost"] = cost
    d.update(kw)
    return d


class TestEfficiency(unittest.TestCase):
    def test_tokens_per_solve_includes_failures(self):
        events = [ev("PASS", 1.0, tokens=100), ev("FAIL", 0.0, tokens=50)]
        self.assertAlmostEqual(scoring.efficiency_per_solve(events, "tokens"), 150.0)

    def test_zero_success_is_na_c44(self):
        events = [ev("FAIL", 0.0, tokens=50)]
        self.assertIsNone(scoring.efficiency_per_solve(events, "tokens"))

    def test_tokens_per_utility(self):
        events = [ev("PARTIAL", 0.5, tokens=100), ev("PARTIAL", 0.5, tokens=100)]
        self.assertAlmostEqual(scoring.tokens_per_utility(events), 200.0)

    def test_cost_missing_is_unavailable_c45(self):
        events = [ev("PASS", 1.0, tokens=10, cost=0.5), ev("FAIL", 0.0, tokens=10)]
        self.assertIsNone(scoring.cost_per_solve(events))
        ok = [ev("PASS", 1.0, tokens=10, cost=0.5), ev("FAIL", 0.0, tokens=10, cost=0.2)]
        self.assertAlmostEqual(scoring.cost_per_solve(ok), 0.7)

    def test_budget_compliance(self):
        self.assertAlmostEqual(scoring.budget_compliance(200, 100), 0.5)
        self.assertAlmostEqual(scoring.budget_compliance(50, 100), 1.0)

    def test_efficiency_score_omits_unavailable(self):
        self.assertAlmostEqual(scoring.efficiency_score([0.5, 1.0, None]), (0.5) ** 0.5)
        self.assertIsNone(scoring.efficiency_score([]))


if __name__ == "__main__":
    unittest.main()
