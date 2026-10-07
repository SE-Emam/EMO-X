"""Tests for generators/mutations.py (stdlib unittest). SPEC 6/9."""

import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(REPO, "shared")
for path in (REPO, SHARED):
    if path not in sys.path:
        sys.path.insert(0, path)

from generators.task_dsl import example_h3_manifest
from generators.instance_factory import build_instance, verify_oracle, prompt_leaks_oracle
from generators.mutations import (
    PRIMARY_VARIANTS,
    VARIANT_LEVELS,
    TRANSFORMS,
    VariantError,
    apply_variant,
    primary_variant,
    variant_level,
)
from generators.seeds import parse_instance_id

try:
    from schemas import SchemaError  # noqa: F401 (re-export parity check)
except ImportError:
    from shared.schemas import SchemaError  # noqa: F401


def canonical(seed=928174):
    return build_instance(example_h3_manifest(), seed)


def h3_spec():
    return example_h3_manifest()["generator"]["parameters"]


def all_variants():
    out = []
    base = canonical()
    out.append(("paraphrase", apply_variant(base, "paraphrase")))
    out.append(("naming", apply_variant(base, "naming")))
    out.append(("constraint", apply_variant(base, "constraint")))
    out.append(("structural", apply_variant(base, "structural", parameters_spec=h3_spec())))
    out.append(("adversarial", apply_variant(base, "adversarial")))
    out.append(("recovery", apply_variant(base, "recovery")))
    out.append(("novel", apply_variant(base, "novel", parameters_spec=h3_spec())))
    return out


class TestVariantExclusivity(unittest.TestCase):
    def test_exactly_one_primary_variant_per_instance(self):
        # DEN C14: every instance carries exactly one primary variant.
        base = canonical()
        self.assertEqual(primary_variant(base), "canonical")
        for name, inst in all_variants():
            with self.subTest(variant=name):
                self.assertEqual(primary_variant(inst), name)
                self.assertEqual(inst["variant"], name)
                self.assertNotIn("variants", inst)

    def test_rejects_missing_plural_or_unknown(self):
        base = canonical()
        bad_missing = dict(base)
        del bad_missing["variant"]
        with self.assertRaises(VariantError):
            primary_variant(bad_missing)
        bad_list = dict(base)
        bad_list["variant"] = ["canonical", "novel"]
        with self.assertRaises(VariantError):
            primary_variant(bad_list)
        bad_plural = dict(base)
        bad_plural["variants"] = ["canonical"]
        with self.assertRaises(VariantError):
            primary_variant(bad_plural)
        bad_unknown = dict(base)
        bad_unknown["variant"] = "hidden-edge"
        with self.assertRaises(VariantError):
            primary_variant(bad_unknown)

    def test_levels_cover_c_p_s_a_r_n(self):
        self.assertEqual(set(VARIANT_LEVELS.values()), {"C", "P", "S", "A", "R", "N"})
        for variant in PRIMARY_VARIANTS:
            self.assertEqual(variant_level(variant), VARIANT_LEVELS[variant])
        with self.assertRaises(VariantError):
            variant_level("hidden-edge")


class TestTransformPurity(unittest.TestCase):
    def test_inputs_never_mutated(self):
        for name, _inst in all_variants():
            with self.subTest(variant=name):
                before = canonical()
                snapshot = copy.deepcopy(before)
                TRANSFORMS[name](
                    before,
                    **({"parameters_spec": h3_spec()} if name in ("structural", "novel") else {}),
                )
                self.assertEqual(before, snapshot)

    def test_transforms_deterministic(self):
        for name, _ in all_variants():
            with self.subTest(variant=name):
                kwargs = {"parameters_spec": h3_spec()} if name in ("structural", "novel") else {}
                first = apply_variant(canonical(), name, **kwargs)
                second = apply_variant(canonical(), name, **kwargs)
                self.assertEqual(first, second)

    def test_instance_id_follows_convention(self):
        for name, inst in all_variants():
            with self.subTest(variant=name):
                family, variant, index = parse_instance_id(inst["instance_id"])
                self.assertEqual((family, variant, index), ("H3", name, 1))
                self.assertIn("derived_from", inst)

    def test_unknown_variant_rejected(self):
        with self.assertRaises(VariantError):
            apply_variant(canonical(), "hidden-edge")
        with self.assertRaises(VariantError):
            apply_variant(canonical(), "canonical")

    def test_novel_needs_spec(self):
        with self.assertRaises(VariantError):
            apply_variant(canonical(), "novel", parameters_spec={})


class TestOraclePreservation(unittest.TestCase):
    def test_oracle_recomputable_after_every_transform(self):
        manifest = example_h3_manifest()
        for name, inst in all_variants():
            with self.subTest(variant=name):
                self.assertTrue(verify_oracle(inst, manifest), msg=name)

    def test_perturbed_params_change_oracle(self):
        base = canonical()
        novel = apply_variant(base, "novel", parameters_spec=h3_spec())
        self.assertNotEqual(base["parameters"], novel["parameters"])
        self.assertNotEqual(base["oracle_hash"], novel["oracle_hash"])

    def test_no_answer_leak_in_any_variant(self):
        # SPEC 6: no generated prompt may embed the expected answer.
        for name, inst in all_variants():
            with self.subTest(variant=name):
                self.assertFalse(
                    prompt_leaks_oracle(inst["prompt"], inst["oracle"]),
                    msg="%s prompt leaks %r" % (name, inst["oracle"].get("expected")),
                )
                if "expected" in inst["oracle"]:
                    self.assertNotIn(str(inst["oracle"]["expected"]), inst["prompt"])

    def test_recovery_marks_recoverable(self):
        inst = apply_variant(canonical(), "recovery")
        self.assertTrue(inst["recoverable"])
        self.assertEqual(inst["parameters"]["injected_fault"], "TOOL_TIMEOUT")


if __name__ == "__main__":
    unittest.main()
