"""Core scoring: B4-B11 + hierarchy C16-C20/C78. Golden numbers hand-checked."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring


def ev(task, inst, variant, trial, status, score, **kw):
    d = {
        "run_id": "R1",
        "model_id": "M",
        "task_family_id": task,
        "instance_id": inst,
        "variant_class": variant,
        "trial_id": trial,
        "primary_status": status,
        "score": score,
    }
    d.update(kw)
    return d


class TestScoreTask(unittest.TestCase):
    def test_b4_example(self):
        s, y = scoring.score_task([1, 1, 0], [0.25, 0.50, 0.25])
        self.assertAlmostEqual(s, 0.75)
        self.assertFalse(y)

    def test_b5_mandatory_gate(self):
        s, y = scoring.score_task([1, 1, 0], [0.25, 0.50, 0.25], mandatory={2})
        self.assertAlmostEqual(s, 0.75)
        self.assertFalse(y)  # C24: gate modifies strict-pass only
        s2, y2 = scoring.score_task([1, 1, 1], [0.25, 0.50, 0.25], mandatory={2})
        self.assertTrue(y2)

    def test_b4_rejects_bad_weights(self):
        with self.assertRaises(ValueError):
            scoring.score_task([1, 0], [0.5, 0.6])


class TestHierarchy(unittest.TestCase):
    def test_trial_instance_variant_family_suite(self):
        # C19: VOID/ERROR trials excluded; all-excluded -> NA
        self.assertIsNone(scoring.aggregate_trials([1.0], ["VOID"]))
        self.assertAlmostEqual(scoring.aggregate_trials([1.0, 0.0], ["PASS", "FAIL"]), 0.5)
        # C16/C17/C12
        self.assertIsNone(scoring.aggregate_instances_to_variant([]))
        self.assertIsNone(scoring.aggregate_instances_to_variant([None]))
        self.assertAlmostEqual(scoring.aggregate_instances_to_variant([1.0, 0.0]), 0.5)
        self.assertIsNone(scoring.aggregate_variants_to_family([None, None]))
        self.assertAlmostEqual(scoring.aggregate_variants_to_family([1.0, None]), 1.0)
        self.assertIsNone(scoring.aggregate_families_to_suite([]))

    def test_variant_balance_blocks_instance_domination(self):
        # C18: 3 canonical @1.0 + 100 novel @0.0 -> family = 0.5, not ~0.03
        fam = scoring.aggregate_variants_to_family([1.0, 0.0])
        self.assertAlmostEqual(fam, 0.5)

    def test_aggregate_events_hierarchy(self):
        events = [
            ev("H3", "i1", "canonical", 1, "PASS", 1.0),
            ev("H3", "i1", "canonical", 2, "VOID", 0.0),
            ev("H3", "i2", "novel", 1, "FAIL", 0.0),
            ev("H3", "i3", "novel", 1, "ERROR", 0.0),
        ]
        out = scoring.aggregate_events(events)
        # i1 -> 1.0 (VOID trial dropped, C19); i3 dropped entirely
        self.assertAlmostEqual(out["instance_scores"][("H3", "canonical", "i1")], 1.0)
        self.assertAlmostEqual(out["family_scores"]["H3"], 0.5)
        self.assertAlmostEqual(out["suite_score"], 0.5)
        self.assertAlmostEqual(out["coverage"], 2 / 4)  # C10

    def test_missing_flags_default_eligible(self):
        events = [ev("T", "i", "canonical", 1, "PASS", 1.0)]
        self.assertAlmostEqual(scoring.pass_rate(events), 1.0)


class TestRates(unittest.TestCase):
    def _events(self):
        return [
            ev("A", "i1", "canonical", 1, "PASS", 1.0),
            ev("A", "i2", "canonical", 1, "FAIL", 0.0),
            ev("B", "i1", "canonical", 1, "PASS", 1.0),
            ev("B", "i2", "canonical", 1, "PASS", 1.0),
            ev("B", "i3", "canonical", 1, "VOID", 0.0),
        ]

    def test_pass_rate(self):
        self.assertAlmostEqual(scoring.pass_rate(self._events()), 3 / 4)

    def test_family_balanced(self):
        # A: 1/2, B: 2/2 -> (0.5+1.0)/2 = 0.75
        self.assertAlmostEqual(scoring.family_balanced_pass_rate(self._events()), 0.75)

    def test_partial_rate(self):
        events = [
            ev("A", "i1", "canonical", 1, "PARTIAL", 0.5),
            ev("A", "i2", "canonical", 1, "PASS", 1.0),
        ]
        self.assertAlmostEqual(scoring.partial_rate(events), 0.5)

    def test_empty_is_na(self):
        self.assertIsNone(scoring.pass_rate([]))
        self.assertIsNone(scoring.partial_rate([]))

    def test_instability(self):
        self.assertAlmostEqual(scoring.instability_from_p(0.5), 1.0)
        self.assertAlmostEqual(scoring.instability_from_p(1.0), 0.0)
        events = [
            ev("A", "i1", "canonical", 1, "PASS", 1.0),
            ev("A", "i2", "canonical", 1, "FAIL", 0.0),
        ]
        self.assertAlmostEqual(scoring.instability(events), 1.0)


class TestAtK(unittest.TestCase):
    def test_pass_at_k_golden(self):
        # n=5,c=3,k=2 -> 1 - C(2,2)/C(5,2) = 0.9
        self.assertAlmostEqual(scoring.pass_at_k(5, 3, 2), 0.9)

    def test_consistency_at_k_golden(self):
        # C(3,2)/C(5,2) = 0.3
        self.assertAlmostEqual(scoring.consistency_at_k(5, 3, 2), 0.3)

    def test_k_gt_n_is_na(self):
        self.assertIsNone(scoring.pass_at_k(2, 1, 3))
        self.assertIsNone(scoring.consistency_at_k(2, 1, 3))

    def test_all_success(self):
        self.assertAlmostEqual(scoring.pass_at_k(3, 3, 2), 1.0)
        self.assertAlmostEqual(scoring.consistency_at_k(3, 3, 2), 1.0)


if __name__ == "__main__":
    unittest.main()
