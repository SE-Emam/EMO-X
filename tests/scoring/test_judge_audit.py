"""Tests for judge auditing (perturbation flip rates)."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "judges")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from judge_audit import (  # noqa: E402
    PERTURBATIONS,
    audit_judge,
    audit_mark,
    perturb,
)


def stable_judge(case):
    """Verdict from evidence keywords only: immune to padding/order."""
    text = (case.get("prompt", "") + " " + " ".join(case.get("candidates", []) or [])).lower()
    return "PASS" if "correct-evidence" in text else "FAIL"


def order_biased_judge(case):
    """Always picks the first candidate: flips on order_swap."""
    cands = case.get("candidates") or ["PASS", "FAIL"]
    return cands[0]


CASES = [
    {
        "id": "c1",
        "prompt": "correct-evidence. " + "Background detail. " * 10,
        "candidates": ["PASS", "FAIL"],
        "alt_language": "قيّم: الدليل موجود.",
    },
    {"id": "c2", "prompt": "Rate: nothing relevant here.", "candidates": ["FAIL", "PASS"]},
]


class JudgeAuditTests(unittest.TestCase):
    def test_stable_judge_no_flips(self):
        audit = audit_judge(CASES, stable_judge)
        for kind in PERTURBATIONS:
            self.assertEqual(audit["flips"][kind], 0.0)
        self.assertEqual(audit["stability"], 1.0)
        self.assertEqual(audit_mark(audit["stability"]), "STABLE")

    def test_order_bias_detected(self):
        audit = audit_judge(CASES, order_biased_judge)
        self.assertEqual(audit["flips"]["order_swap"], 1.0)
        self.assertEqual(audit_mark(audit["stability"]), "UNSTABLE")

    def test_noop_excluded_not_zero(self):
        # language_dual without alt_language is a no-op for c2 only;
        # c1 still counts, so the rate is defined over applicable cases.
        audit = audit_judge(CASES, stable_judge, kinds=["language_dual"])
        self.assertEqual(audit["flips"]["language_dual"], 0.0)

    def test_unknown_perturbation_rejected(self):
        with self.assertRaises(ValueError):
            perturb(CASES[0], "mind_reading")

    def test_pure_no_mutation(self):
        before = dict(CASES[0])
        perturb(CASES[0], "verbosity_pad")
        self.assertEqual(CASES[0], before)


if __name__ == "__main__":
    unittest.main()
