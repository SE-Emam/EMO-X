"""Tests for H3 dynamic equations: varied surface, preserved truth (SPEC 9).

H3.seed -> numbers/names/representation/wording/context vary, while the
oracle kind stays fixed (unique solution of a*v=b mod m). Run via:
python3 tests/run_all.py (or unittest discover -s tests/generators).
"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "generators"),
           os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from instance_factory import build_h3_equation, check_h3_equation  # noqa: E402


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


class H3DynamicTests(unittest.TestCase):
    def test_determinism(self):
        a = build_h3_equation(928174, variant="perturbed", index=1)
        b = build_h3_equation(928174, variant="perturbed", index=1)
        self.assertEqual(a["instance_hash"], b["instance_hash"])
        self.assertEqual(a["prompt"], b["prompt"])

    def test_five_distinct_surfaces_same_oracle_kind(self):
        prompts, kinds = set(), set()
        for i, seed in enumerate((11, 22, 33, 44, 55), start=1):
            inst = build_h3_equation(seed, variant="novel", index=i)
            prompts.add(inst["prompt"])
            kinds.add(inst["oracle"]["oracle_type"])
            p = inst["parameters"]
            self.assertEqual(_gcd(p["coefficient"], p["modulus"]), 1)
            self.assertEqual(inst["oracle"]["expected"],
                             (pow(p["coefficient"], -1, p["modulus"])
                              * p["target"]) % p["modulus"])
        self.assertEqual(len(prompts), 5)  # H3-A..E all differ
        self.assertEqual(kinds, {"deterministic"})

    def test_oracle_self_verifies_and_rejects(self):
        inst = build_h3_equation(7, variant="perturbed", index=1)
        exp = inst["oracle"]["expected"]
        mod = inst["parameters"]["modulus"]
        ok, _ = check_h3_equation("x = %d" % exp, exp)
        self.assertTrue(ok)
        ok, _ = check_h3_equation(str(exp), exp)
        self.assertTrue(ok)
        wrong = (exp + 1) % mod
        if wrong != exp:
            ok, _ = check_h3_equation("x = %d" % wrong, exp)
            self.assertFalse(ok)

    def test_no_answer_leak_perturbed(self):
        for seed in (1, 2, 3):
            inst = build_h3_equation(seed, variant="perturbed", index=1)
            exp = inst["oracle"]["expected"]
            # The answer must never be presented as the solution.
            self.assertNotIn("= %d" % exp, inst["prompt"])

    def test_instance_id_convention(self):
        inst = build_h3_equation(5, variant="novel", index=3)
        self.assertEqual(inst["instance_id"], "H3-novel-00003")
        self.assertEqual(inst["variant"], "novel")

    def test_bad_variant_rejected(self):
        from schemas import SchemaError
        with self.assertRaises(SchemaError):
            build_h3_equation(1, variant="canonical", index=1)

    def test_executor_variants(self):
        sys.path.insert(0, os.path.join(_ROOT, "suites", "code-bench-25"))
        sys.path.insert(0, os.path.join(_ROOT, "suites"))
        import executor as exc
        self.assertIn("perturbed", exc.VARIANTS)
        self.assertIn("novel", exc.VARIANTS)

        def chat_ok(messages, **kw):
            inst = build_h3_equation(9, variant="perturbed", index=1)
            return "x = %d" % inst["oracle"]["expected"], 0.1, {}

        rec, _ = exc.run_family("H3", chat_ok, run_id="R", model_id="m",
                                trial_id=1, index=1, seed=9,
                                variant="perturbed")
        self.assertEqual(rec["primary_status"], "PASS")
        self.assertEqual(rec["variant_class"], "perturbed")

        def chat_bad(messages, **kw):
            return "x = 999999", 0.1, {}

        rec, _ = exc.run_family("H3", chat_bad, run_id="R", model_id="m",
                                trial_id=1, index=2, seed=9,
                                variant="novel")
        self.assertEqual(rec["primary_status"], "FAIL")

        with self.assertRaises(TypeError):  # skip contract (DEN: NA)
            exc.run_family("H4", chat_ok, run_id="R", model_id="m",
                           trial_id=1, index=1, seed=9, variant="novel")


if __name__ == "__main__":
    unittest.main()
