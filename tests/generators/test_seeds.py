"""Tests for generators/seeds.py (stdlib unittest). SPEC 8."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(REPO, "shared")
for path in (REPO, SHARED):
    if path not in sys.path:
        sys.path.insert(0, path)

from generators.seeds import (GENERATOR_VERSION, make_rng, stream_tag,
                              derive_child_seed, make_instance_id,
                              parse_instance_id, canonical_hash,
                              build_instance_record)
# Import SchemaError exactly the way generators resolve it (bare
# `schemas` first, package fallback second) so assertRaises matches.
try:
    from schemas import SchemaError
except ImportError:
    from shared.schemas import SchemaError
try:
    from manifests import sha256_manifest
except ImportError:
    from shared.manifests import sha256_manifest


class TestSeedStreams(unittest.TestCase):
    def test_same_seed_twice_identical_stream(self):
        a = make_rng(928174, "1.2.0")
        b = make_rng(928174, "1.2.0")
        self.assertEqual([a.randint(0, 10**9) for _ in range(20)],
                         [b.randint(0, 10**9) for _ in range(20)])

    def test_stream_tag_format(self):
        self.assertEqual(stream_tag(928174, "1.2.0"), "1.2.0:928174")

    def test_different_seeds_differ(self):
        a = make_rng(1, "1.0.0")
        b = make_rng(2, "1.0.0")
        self.assertNotEqual([a.random() for _ in range(5)],
                            [b.random() for _ in range(5)])

    def test_version_bump_rebaselines_stream(self):
        a = make_rng(7, "1.0.0")
        b = make_rng(7, "2.0.0")
        self.assertNotEqual([a.random() for _ in range(5)],
                            [b.random() for _ in range(5)])

    def test_rejects_bool_and_non_int_seed(self):
        with self.assertRaises(SchemaError):
            make_rng(True, "1.0.0")
        with self.assertRaises(SchemaError):
            make_rng("928174", "1.0.0")

    def test_rejects_empty_version(self):
        with self.assertRaises(SchemaError):
            make_rng(1, "")


class TestInstanceIds(unittest.TestCase):
    def test_convention_example(self):
        self.assertEqual(make_instance_id("H3", "canonical", 1),
                         "H3-canonical-00001")

    def test_zero_padded_index(self):
        self.assertEqual(make_instance_id("T2", "novel", 42),
                         "T2-novel-00042")

    def test_round_trip(self):
        iid = make_instance_id("H3", "recovery", 7)
        self.assertEqual(parse_instance_id(iid), ("H3", "recovery", 7))

    def test_rejects_bad_ids(self):
        for bad in ("H3-canonical-1", "H3-canonical-0001",
                    "H3-canonical-000001", "H3-canonical",
                    "H3-canonical-abcde", "", None):
            with self.assertRaises(SchemaError, msg=repr(bad)):
                parse_instance_id(bad)

    def test_rejects_hyphen_variant(self):
        with self.assertRaises(SchemaError):
            make_instance_id("H3", "hidden-edge", 1)


class TestInstanceRecords(unittest.TestCase):
    def _record(self, seed=928174):
        return build_instance_record(
            "H3", seed, "1.2.0",
            {"coefficient": 3, "modulus": 7, "target": 100},
            {"oracle_type": "deterministic", "task": "H3", "expected": 4})

    def test_record_keys_match_spec8(self):
        rec = self._record()
        self.assertEqual(sorted(rec),
                         ["generator_version", "instance_hash",
                          "oracle_hash", "seed", "task"])

    def test_same_inputs_identical_hashes(self):
        self.assertEqual(self._record(), self._record())

    def test_seed_change_changes_instance_hash(self):
        self.assertNotEqual(self._record(1)["instance_hash"],
                            self._record(2)["instance_hash"])

    def test_uses_b58_manifest_hash(self):
        rec = self._record()
        self.assertEqual(rec["instance_hash"], sha256_manifest({
            "generator_version": "1.2.0",
            "parameters": {"coefficient": 3, "modulus": 7, "target": 100},
            "seed": 928174, "task": "H3", "variant": "canonical"}))
        self.assertEqual(rec["oracle_hash"], sha256_manifest(
            {"oracle_type": "deterministic", "task": "H3", "expected": 4}))
        self.assertEqual(len(rec["instance_hash"]), 64)

    def test_canonical_hash_alias(self):
        self.assertEqual(canonical_hash({"b": 1, "a": 2}),
                         sha256_manifest({"a": 2, "b": 1}))

    def test_child_seed_deterministic(self):
        self.assertEqual(derive_child_seed(5, "1.0.0", "novel"),
                         derive_child_seed(5, "1.0.0", "novel"))
        self.assertNotEqual(derive_child_seed(5, "1.0.0", "novel"),
                            derive_child_seed(5, "1.0.0", "structural"))
        self.assertNotEqual(derive_child_seed(5, "1.0.0", "novel"),
                            derive_child_seed(6, "1.0.0", "novel"))


if __name__ == "__main__":
    unittest.main()
