"""Y-8 manifest single-source-of-truth guard (stdlib unittest).

For all 29 code-bench-25 families asserts:
  manifest["prompt"] == cases.prompt_text(family) byte-identically,
  oracle/timeouts/forbidden_paths present, H3 generator v1.1 intact.

Y-INT flips the executor to read manifests with this test as guard.

Run: python3 -m unittest discover -s tests/backends -v
"""

import importlib.util
import json
import os
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CB25 = os.path.join(ROOT, "suites", "code-bench-25")
MANDIR = os.path.join(CB25, "manifests")
CASES_PATH = os.path.join(CB25, "cases.py")


def _load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cb_cases = _load_by_path("cb25_cases_truth", CASES_PATH)


def _load_manifest(family):
    path = os.path.join(MANDIR, family + ".json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestManifestTruth(unittest.TestCase):
    def test_29_families_covered(self):
        self.assertEqual(len(cb_cases.FAMILY_IDS), 29)
        got = sorted(f[:-5] for f in os.listdir(MANDIR) if f.endswith(".json"))
        self.assertEqual(len(got), 29)
        for fam in cb_cases.FAMILY_IDS:
            self.assertIn(fam, got)

    def test_prompt_byte_identical(self):
        for fam in sorted(cb_cases.FAMILY_IDS):
            with self.subTest(family=fam):
                m = _load_manifest(fam)
                self.assertIn("prompt", m)
                want = cb_cases.prompt_text(fam)
                self.assertEqual(m["prompt"], want)
                self.assertEqual(m["prompt"].encode("utf-8"), want.encode("utf-8"))

    def test_oracle_present(self):
        for fam in sorted(cb_cases.FAMILY_IDS):
            with self.subTest(family=fam):
                m = _load_manifest(fam)
                oracle = m.get("oracle")
                self.assertIsInstance(oracle, dict)
                self.assertIsInstance(oracle.get("type"), str)
                self.assertTrue(oracle["type"])
                self.assertIsInstance(oracle.get("check"), str)
                self.assertTrue(oracle["check"])

    def test_timeouts_present(self):
        for fam in sorted(cb_cases.FAMILY_IDS):
            with self.subTest(family=fam):
                m = _load_manifest(fam)
                timeouts = m.get("timeouts")
                self.assertIsInstance(timeouts, dict)
                for key in ("generation_seconds", "execution_seconds"):
                    val = timeouts.get(key)
                    self.assertIsInstance(val, int, key)
                    self.assertGreater(val, 0, key)

    def test_forbidden_paths_present(self):
        for fam in sorted(cb_cases.FAMILY_IDS):
            with self.subTest(family=fam):
                m = _load_manifest(fam)
                fps = m.get("forbidden_paths")
                self.assertIsInstance(fps, list)
                self.assertTrue(fps)
                for entry in fps:
                    self.assertIsInstance(entry, str)
                    self.assertTrue(entry)
                self.assertIn("/etc", fps)
                self.assertIn("~/.ssh", fps)

    def test_h3_generator_v1_1_intact(self):
        m = _load_manifest("H3")
        self.assertEqual(m["id"], "H3")
        self.assertEqual(m["version"], "1.1")
        gen = m.get("generator")
        self.assertIsInstance(gen, dict)
        self.assertEqual(gen.get("type"), "parametric")
        self.assertEqual(gen.get("seed"), "random")
        params = gen.get("parameters")
        self.assertIsInstance(params, dict)
        for key in ("modulus", "coefficient", "target", "form", "variable", "context"):
            self.assertIn(key, params)

    def test_manifest_ids_match_filenames(self):
        for fam in sorted(cb_cases.FAMILY_IDS):
            with self.subTest(family=fam):
                m = _load_manifest(fam)
                self.assertEqual(m["id"], fam)


if __name__ == "__main__":
    unittest.main()
