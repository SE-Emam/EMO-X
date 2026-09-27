"""H3 math-subtype goldens: linear vs exponentiation (SPEC 9, P0-08).

The frozen canonical H3 prompt (shared/PROMPT_PACK_v1.md) is modular
EXPONENTIATION (remainder of 3^100 divided by 7). build_h3_equation
serves both subtypes: "linear" (legacy a*v == b mod m, default) and
"exp" (c^t mod m, matching the canonical oracle kind). Golden
pins below are hand-verified: expected == pow(base, exponent, modulus)
for exp, and the legacy closed form for linear.

Run via: python3 tests/run_all.py (or unittest discover -s tests/generators).
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

from instance_factory import (  # noqa: E402
    H3_SUBTYPES, build_h3_equation, check_h3_equation)


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


class H3SubtypeGoldenTests(unittest.TestCase):
    def test_exp_golden_perturbed(self):
        # Pinned oracle: pow(11, 133, 32) == 27.
        inst = build_h3_equation(7, variant="perturbed", index=1,
                                 subtype="exp")
        self.assertEqual(inst["task_name"], "modular_exponentiation")
        self.assertEqual(inst["parameters"]["base"], 11)
        self.assertEqual(inst["parameters"]["exponent"], 133)
        self.assertEqual(inst["parameters"]["modulus"], 32)
        self.assertEqual(inst["oracle"]["expected"], 27)
        self.assertEqual(inst["oracle"]["expected"],
                         pow(11, 133, 32))

    def test_exp_golden_novel(self):
        # Same draws as perturbed seed 7 (novel only changes surface):
        # pow(11, 133, 32) == 27, prompt carries noise context.
        inst = build_h3_equation(7, variant="novel", index=1,
                                 subtype="exp")
        self.assertEqual(inst["oracle"]["expected"], 27)
        self.assertEqual(inst["oracle"]["expected"],
                         pow(inst["parameters"]["base"],
                             inst["parameters"]["exponent"],
                             inst["parameters"]["modulus"]))

    def test_linear_golden_perturbed(self):
        # Legacy closed form: (inv(63) * 145) mod 65 == 25.
        inst = build_h3_equation(7, variant="perturbed", index=1,
                                 subtype="linear")
        self.assertEqual(inst["task_name"], "modular_equation")
        self.assertEqual(inst["oracle"]["expected"], 25)
        p = inst["parameters"]
        self.assertEqual(inst["oracle"]["expected"],
                         (pow(p["coefficient"], -1, p["modulus"])
                          * p["target"]) % p["modulus"])

    def test_exp_oracle_matches_pow_across_seeds(self):
        for seed in (1, 2, 3, 928174):
            for variant in ("perturbed", "novel"):
                inst = build_h3_equation(seed, variant=variant, index=1,
                                         subtype="exp")
                p = inst["parameters"]
                self.assertEqual(inst["oracle"]["oracle_type"],
                                 "deterministic")
                self.assertEqual(inst["oracle"]["expected"],
                                 pow(p["base"], p["exponent"],
                                     p["modulus"]))
                self.assertTrue(0 <= inst["oracle"]["expected"]
                                < p["modulus"])

    def test_exp_check_accepts_and_rejects(self):
        inst = build_h3_equation(7, variant="perturbed", index=1,
                                 subtype="exp")
        exp = inst["oracle"]["expected"]
        ok, _ = check_h3_equation(str(exp), exp, subtype="exp")
        self.assertTrue(ok)
        ok, _ = check_h3_equation("the remainder is %d" % exp, exp,
                                  subtype="exp")
        self.assertTrue(ok)
        wrong = (exp + 1) % inst["parameters"]["modulus"]
        if wrong != exp:
            ok, _ = check_h3_equation("result = %d" % wrong, exp,
                                      subtype="exp")
            self.assertFalse(ok)

    def test_exp_no_answer_leak(self):
        for seed in (1, 2, 3):
            for variant in ("perturbed", "novel"):
                inst = build_h3_equation(seed, variant=variant, index=1,
                                         subtype="exp")
                self.assertNotIn("= %d" % inst["oracle"]["expected"],
                                 inst["prompt"])
                self.assertNotIn("== %d" % inst["oracle"]["expected"],
                                 inst["prompt"])

    def test_bad_subtype_rejected(self):
        from schemas import SchemaError
        with self.assertRaises(SchemaError):
            build_h3_equation(1, variant="perturbed", index=1,
                              subtype="modexp")
        with self.assertRaises(SchemaError):
            check_h3_equation("4", 4, subtype="modexp")

    def test_subtype_spellings(self):
        self.assertEqual(tuple(H3_SUBTYPES), ("linear", "exp"))


class H3SubtypeDeterminismTests(unittest.TestCase):
    def test_exp_determinism(self):
        a = build_h3_equation(928174, variant="perturbed", index=1,
                              subtype="exp")
        b = build_h3_equation(928174, variant="perturbed", index=1,
                              subtype="exp")
        self.assertEqual(a["instance_hash"], b["instance_hash"])
        self.assertEqual(a["prompt"], b["prompt"])
        self.assertEqual(a["oracle"], b["oracle"])

    def test_novel_exp_determinism(self):
        a = build_h3_equation(33, variant="novel", index=4,
                              subtype="exp")
        b = build_h3_equation(33, variant="novel", index=4,
                              subtype="exp")
        self.assertEqual(a["instance_hash"], b["instance_hash"])
        self.assertEqual(a["prompt"], b["prompt"])

    def test_linear_default_is_legacy(self):
        # subtype="linear" (default) is byte-identical to the
        # pre-P0-08 generator: same prompt, same hashes.
        default = build_h3_equation(928174, variant="perturbed",
                                    index=1)
        explicit = build_h3_equation(928174, variant="perturbed",
                                     index=1, subtype="linear")
        self.assertEqual(default["prompt"], explicit["prompt"])
        self.assertEqual(default["instance_hash"],
                         explicit["instance_hash"])
        self.assertEqual(default["oracle"], explicit["oracle"])

    def test_subtypes_differ_same_seed(self):
        lin = build_h3_equation(7, variant="perturbed", index=1,
                                subtype="linear")
        exp = build_h3_equation(7, variant="perturbed", index=1,
                                subtype="exp")
        self.assertNotEqual(lin["prompt"], exp["prompt"])
        self.assertNotEqual(lin["instance_hash"], exp["instance_hash"])

    def test_exp_instance_id_convention(self):
        inst = build_h3_equation(5, variant="novel", index=3,
                                 subtype="exp")
        self.assertEqual(inst["instance_id"], "H3-novel-00003")
        self.assertEqual(inst["variant"], "novel")


class H3ExecutorSubtypeTests(unittest.TestCase):
    def test_executor_resolves_exp_from_manifest(self):
        sys.path.insert(0, os.path.join(_ROOT, "suites", "code-bench-25"))
        sys.path.insert(0, os.path.join(_ROOT, "suites"))
        import executor as exc
        manifest = {"math_subtype": {
            "canonical": "modular_exponentiation",
            "perturbed": "modular_exponentiation",
            "novel": "modular_exponentiation"}}
        self.assertEqual(exc._h3_math_subtype("perturbed", manifest),
                         "exp")
        self.assertEqual(exc._h3_math_subtype("novel", manifest), "exp")
        self.assertEqual(exc._h3_math_subtype("perturbed", {}), "linear")
        # No manifest passed: resolves from the suite H3.json field.
        self.assertEqual(exc._h3_math_subtype("perturbed"), "exp")

    def test_executor_exp_roundtrip(self):
        sys.path.insert(0, os.path.join(_ROOT, "suites", "code-bench-25"))
        sys.path.insert(0, os.path.join(_ROOT, "suites"))
        import executor as exc

        def chat_ok(messages, **kw):
            inst = build_h3_equation(9, variant="perturbed", index=1,
                                     subtype="exp")
            return "result = %d" % inst["oracle"]["expected"], 0.1, {}

        rec, _ = exc.run_family("H3", chat_ok, run_id="R", model_id="m",
                                trial_id=1, index=1, seed=9,
                                variant="perturbed", subtype="exp")
        self.assertEqual(rec["primary_status"], "PASS")
        self.assertEqual(rec["variant_class"], "perturbed")

    def test_executor_explicit_linear_preserved(self):
        sys.path.insert(0, os.path.join(_ROOT, "suites", "code-bench-25"))
        sys.path.insert(0, os.path.join(_ROOT, "suites"))
        import executor as exc

        def chat_ok(messages, **kw):
            inst = build_h3_equation(9, variant="perturbed", index=1,
                                     subtype="linear")
            return "x = %d" % inst["oracle"]["expected"], 0.1, {}

        rec, _ = exc.run_family("H3", chat_ok, run_id="R", model_id="m",
                                trial_id=1, index=1, seed=9,
                                variant="perturbed", subtype="linear")
        self.assertEqual(rec["primary_status"], "PASS")


if __name__ == "__main__":
    unittest.main()
