"""Tests for SPEC 36 backend capability manifests (X-5 follow-up).

Run via: python3 tests/run_all.py  (or python3 -m unittest discover -s tests/backends)
Direct pytest-style invocation needs shared/ on sys.path (see tests/README.md).
"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backends import (  # noqa: E402
    CAPABILITY_FIELDS,
    MATERIAL_FIELDS,
    PROVIDER_PROFILES,
    comparability,
    get_capability_manifest,
)


class CapabilityManifestTests(unittest.TestCase):
    def test_all_backends_expose_all_fields(self):
        for backend in ("kaggle", "colab", "openai-generic"):
            man = get_capability_manifest(backend)
            for field in CAPABILITY_FIELDS:
                self.assertIn(field, man, (backend, field))

    def test_all_profiles_expose_all_fields(self):
        for profile in PROVIDER_PROFILES:
            man = get_capability_manifest("openai-generic", profile)
            for field in CAPABILITY_FIELDS:
                self.assertIn(field, man, (profile, field))

    def test_default_profile_is_conservative_unknown(self):
        man = get_capability_manifest("openai-generic")
        self.assertEqual(man["provider_profile"], "unknown")
        self.assertIn("unknown", [man[f] for f in MATERIAL_FIELDS])

    def test_unknown_backend_raises(self):
        with self.assertRaises(ValueError):
            get_capability_manifest("nope")

    def test_unknown_profile_falls_back_to_unknown(self):
        man = get_capability_manifest("openai-generic", "mystery-provider")
        self.assertEqual(man["provider_profile"], "unknown")

    def test_self_comparison_direct(self):
        man = get_capability_manifest("openai-generic", "openai")
        verdict, _ = comparability(man, dict(man))
        self.assertEqual(verdict, "DIRECT")

    def test_kaggle_colab_direct(self):
        verdict, _ = comparability(
            get_capability_manifest("kaggle"), get_capability_manifest("colab")
        )
        self.assertEqual(verdict, "DIRECT")

    def test_material_conflict_non_comparable(self):
        a = get_capability_manifest("openai-generic", "openai")
        b = get_capability_manifest("openai-generic", "deepseek")
        # vision: supported vs unsupported, both verified -> conflict.
        self.assertNotEqual(a["vision"], b["vision"])
        verdict, reason = comparability(a, b)
        self.assertEqual(verdict, "NON_COMPARABLE")
        self.assertIn("vision", reason)

    def test_unknown_forces_conditional(self):
        a = get_capability_manifest("openai-generic")  # unknown-heavy
        b = get_capability_manifest("openai-generic", "openai")
        verdict, _ = comparability(a, b)
        self.assertEqual(verdict, "CONDITIONALLY_COMPARABLE")

    def test_same_path_different_provider_not_direct(self):
        # The user's core rule: /v1/chat/completions equality proves nothing.
        a = get_capability_manifest("openai-generic", "openai")
        b = get_capability_manifest("openai-generic", "openrouter")
        verdict, _ = comparability(a, b)
        self.assertNotEqual(verdict, "DIRECT")


class ManifestComparabilityTests(unittest.TestCase):
    def test_hash_mismatch_wins_over_equal_backends(self):
        from manifests import comparability_with_capabilities

        key_a = {"prompt_sha256": "p1", "harness_sha256": "h", "manifest_sha256": "m"}
        key_b = {"prompt_sha256": "p2", "harness_sha256": "h", "manifest_sha256": "m"}
        cap = get_capability_manifest("kaggle")
        verdict, reason = comparability_with_capabilities(key_a, key_b, cap, dict(cap))
        self.assertEqual(verdict, "NON_COMPARABLE")
        self.assertIn("B58", reason)

    def test_equal_hashes_equal_caps_direct(self):
        from manifests import comparability_with_capabilities

        key = {"prompt_sha256": "p", "harness_sha256": "h", "manifest_sha256": "m"}
        cap = get_capability_manifest("openai-generic", "openai")
        verdict, _ = comparability_with_capabilities(key, dict(key), cap, dict(cap))
        self.assertEqual(verdict, "DIRECT")


if __name__ == "__main__":
    unittest.main()
