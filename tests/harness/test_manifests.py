"""Tests for shared/manifests.py (stdlib unittest). SPEC 7, B58."""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import manifests
from schemas import SchemaError


def good_manifest():
    return {"id": "H3", "version": "1.0", "name": "modular_arithmetic",
            "category": "reasoning", "capabilities": ["generalization"],
            "generator": {"type": "parametric"},
            "difficulty": {"base": 3}, "execution": {"type": "python"},
            "oracle": {"type": "deterministic"},
            "scoring": {"correctness": 1.0}, "variants": ["canonical"],
            "timeouts": {"execution_seconds": 30},
            "network": {"allowed": False},
            "filesystem": {"sandbox_only": True}}


class TestManifests(unittest.TestCase):
    def test_load_from_dict(self):
        out = manifests.load_task_manifest(good_manifest())
        self.assertEqual(out["id"], "H3")

    def test_load_from_json_string(self):
        out = manifests.load_task_manifest(json.dumps(good_manifest()))
        self.assertEqual(out["name"], "modular_arithmetic")

    def test_load_from_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as f:
            json.dump(good_manifest(), f)
            path = f.name
        try:
            out = manifests.load_task_manifest(path)
            self.assertEqual(out["id"], "H3")
        finally:
            os.unlink(path)

    def test_reject_bad_json(self):
        with self.assertRaises(SchemaError):
            manifests.load_task_manifest("{not json")

    def test_reject_missing_field(self):
        bad = good_manifest()
        del bad["oracle"]
        with self.assertRaises(SchemaError):
            manifests.load_task_manifest(bad)

    def test_hash_stable(self):
        a = manifests.sha256_manifest(good_manifest())
        b = manifests.sha256_manifest(dict(good_manifest()))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_hash_changes_on_edit(self):
        a = manifests.sha256_manifest(good_manifest())
        other = good_manifest()
        other["version"] = "2.0"
        self.assertNotEqual(a, manifests.sha256_manifest(other))

    def test_file_hash(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write(b"prompt-pack-bytes")
            path = f.name
        try:
            self.assertEqual(manifests.sha256_file(path),
                             manifests.sha256_bytes(b"prompt-pack-bytes"))
        finally:
            os.unlink(path)

    def test_comparison_key(self):
        k1 = manifests.comparison_key("p", "h", "m")
        k2 = manifests.comparison_key("p", "h", "m")
        k3 = manifests.comparison_key("p", "h", "other")
        self.assertTrue(manifests.is_directly_comparable(k1, k2))
        self.assertFalse(manifests.is_directly_comparable(k1, k3))


if __name__ == "__main__":
    unittest.main()
