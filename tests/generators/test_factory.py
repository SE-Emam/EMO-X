"""Tests for generators/instance_factory.py (stdlib unittest). SPEC 6/7/8."""

import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(REPO, "shared")
for path in (REPO, SHARED):
    if path not in sys.path:
        sys.path.insert(0, path)

from generators.task_dsl import example_h3_manifest, TaskDSL
from generators.instance_factory import (build_instance, verify_oracle,
                                         compute_oracle, render_prompt,
                                         resolve_parameters,
                                         prompt_leaks_oracle)
from generators.seeds import make_rng, parse_instance_id
try:
    from schemas import SchemaError
except ImportError:
    from shared.schemas import SchemaError
try:
    from manifests import sha256_manifest as _sha256_manifest
except ImportError:
    from shared.manifests import sha256_manifest as _sha256_manifest


def h3_manifest():
    return example_h3_manifest()


class TestCanonicalInstances(unittest.TestCase):
    def test_same_seed_manifest_identical_hash(self):
        a = build_instance(h3_manifest(), 928174)
        b = build_instance(h3_manifest(), 928174)
        self.assertEqual(a["instance_hash"], b["instance_hash"])
        self.assertEqual(a["oracle_hash"], b["oracle_hash"])
        self.assertEqual(a, b)

    def test_json_round_trip_stable(self):
        # Simulates "another machine": manifest + instance cross a
        # JSON boundary, then the instance is rebuilt from scratch.
        manifest = json.loads(json.dumps(h3_manifest()))
        first = build_instance(manifest, 424242)
        clone = json.loads(json.dumps(first))
        rebuilt = build_instance(manifest, 424242)
        self.assertEqual(first["instance_hash"], rebuilt["instance_hash"])
        self.assertEqual(clone["instance_hash"], rebuilt["instance_hash"])

    def test_different_seeds_differ(self):
        a = build_instance(h3_manifest(), 1)
        b = build_instance(h3_manifest(), 2)
        self.assertNotEqual(a["instance_hash"], b["instance_hash"])

    def test_instance_id_convention(self):
        inst = build_instance(h3_manifest(), 928174, index=1)
        self.assertEqual(inst["instance_id"], "H3-canonical-00001")
        self.assertEqual(parse_instance_id(inst["instance_id"]),
                         ("H3", "canonical", 1))

    def test_factory_rejects_non_canonical_variant(self):
        with self.assertRaises(SchemaError):
            build_instance(h3_manifest(), 1, variant="novel")

    def test_oracle_recomputable(self):
        inst = build_instance(h3_manifest(), 928174)
        self.assertTrue(verify_oracle(inst, h3_manifest()))
        self.assertTrue(verify_oracle(inst, "modular_arithmetic"))

    def test_oracle_matches_closed_form(self):
        inst = build_instance(h3_manifest(), 928174)
        params = inst["parameters"]
        self.assertEqual(
            inst["oracle"]["expected"],
            pow(int(params["coefficient"]), int(params["target"]),
                int(params["modulus"])))

    def test_no_answer_leak(self):
        # Distinctive sentinel oracle: the prompt must not contain it.
        manifest = h3_manifest()
        inst = build_instance(manifest, 928174)
        self.assertFalse(prompt_leaks_oracle(inst["prompt"], inst["oracle"]))
        self.assertNotIn(str(inst["oracle"]["expected"]), inst["prompt"])

    def test_parameters_within_spec_ranges(self):
        spec = h3_manifest()["generator"]["parameters"]
        inst = build_instance(h3_manifest(), 99)
        self.assertTrue(spec["modulus"]["min"]
                        <= inst["parameters"]["modulus"]
                        <= spec["modulus"]["max"])

    def test_task_dsl_object_accepted(self):
        task = TaskDSL.from_dict(h3_manifest())
        inst = build_instance(task, 5)
        self.assertEqual(inst["task"], "H3")


class TestParameterResolution(unittest.TestCase):
    def test_sorted_key_draw_order_stable(self):
        spec = {"z": {"min": 1, "max": 9}, "a": {"min": 1, "max": 9}}
        first = resolve_parameters(spec, make_rng(3, "1.0.0"))
        second = resolve_parameters(
            {"a": spec["a"], "z": spec["z"]}, make_rng(3, "1.0.0"))
        self.assertEqual(first, second)

    def test_choices_and_const(self):
        spec = {"c": {"choices": ["x", "y"]}, "k": {"const": 7},
                "plain": 42}
        out = resolve_parameters(spec, make_rng(1, "1.0.0"))
        self.assertIn(out["c"], ("x", "y"))
        self.assertEqual(out["k"], 7)
        self.assertEqual(out["plain"], 42)

    def test_rejects_bad_range(self):
        with self.assertRaises(SchemaError):
            resolve_parameters({"p": {"min": 9, "max": 1}},
                               make_rng(1, "1.0.0"))

    def test_generic_oracle_digest_recomputable(self):
        oracle = compute_oracle("T9", "other_task", {"alpha": 1})
        self.assertIn("params_digest", oracle)
        inst = {"task": "T9", "parameters": {"alpha": 1},
                "oracle": copy.deepcopy(oracle),
                "oracle_hash": oracle_hash_of(oracle)}
        self.assertTrue(verify_oracle(inst, "other_task"))

    def test_render_generic_prompt(self):
        manifest = {"id": "T9", "name": "other_task"}
        prompt = render_prompt(manifest, {"alpha": 1})
        self.assertIn("alpha=1", prompt)


def oracle_hash_of(oracle):
    return _sha256_manifest(oracle)


if __name__ == "__main__":
    unittest.main()
