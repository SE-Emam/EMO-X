"""Y-4 hidden-suite tests (stdlib unittest).

Covers: manifest validity + visibility hidden + no stored instances,
determinism (same seed => same hash), instances never written to the
repo, scope gate (refuses without scope), oracle correctness.

Run: python3 -m unittest tests.backends.test_hidden -v
"""

import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", ".."))
SHARED = os.path.join(ROOT, "shared")
HIDDEN = os.path.join(ROOT, "suites", "code-bench-25-hidden")
MANIFESTS = os.path.join(HIDDEN, "manifests")

for _p in (SHARED, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import manifests as manifest_lib  # noqa: E402


def _load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


hidden_cases = _load_by_path("hidden_cases_under_test",
                             os.path.join(HIDDEN, "cases.py"))
hidden_executor = _load_by_path("hidden_executor_under_test",
                                os.path.join(HIDDEN, "executor.py"))

FAMILIES = ("HH1", "HH2", "HH3")


def _stub_chat_factory(reply_fn):
    def chat(messages, **kw):
        return reply_fn(messages), 0.1, {}
    return chat


def _snapshot_files(top):
    found = set()
    for dirpath, _dirnames, filenames in os.walk(top):
        for name in filenames:
            found.add(os.path.relpath(os.path.join(dirpath, name), top))
    return found


class TestHiddenManifests(unittest.TestCase):
    def test_three_manifests_validate(self):
        files = sorted(f for f in os.listdir(MANIFESTS) if f.endswith(".json"))
        self.assertEqual(files, ["HH1.json", "HH2.json", "HH3.json"])
        for name in files:
            with self.subTest(manifest=name):
                manifest = manifest_lib.load_task_manifest(
                    os.path.join(MANIFESTS, name))
                self.assertEqual(manifest["id"], name[:-5])
                self.assertEqual(manifest.get("visibility"), "hidden")
                self.assertIn("hidden", manifest["variants"])

    def test_manifests_hold_config_only(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                with open(os.path.join(MANIFESTS, family + ".json"),
                          encoding="utf-8") as f:
                    raw = json.load(f)
                for banned in ("instances", "prompt", "prompts", "seeds",
                               "answers", "expected"):
                    self.assertNotIn(banned, raw)
                self.assertIn("parameters", raw["generator"])
                self.assertEqual(raw["oracle"]["type"], "deterministic")


class TestHiddenDeterminism(unittest.TestCase):
    def test_same_seed_same_hash(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                first = hidden_cases.make_instance(family, 25000, 1)
                second = hidden_cases.make_instance(family, 25000, 1)
                self.assertEqual(first["instance_hash"],
                                 second["instance_hash"])
                self.assertEqual(first["oracle_hash"],
                                 second["oracle_hash"])
                self.assertEqual(first["prompt"], second["prompt"])

    def test_different_seeds_differ(self):
        seen = set()
        for family in FAMILIES:
            inst = hidden_cases.make_instance(family, 4242, 3)
            seen.add(inst["instance_hash"])
        self.assertEqual(len(seen), len(FAMILIES))

    def test_prompt_pack_hash_stable_and_config_only(self):
        before = hidden_executor.prompt_pack_sha256()
        hidden_cases.make_instance("HH1", 7, 1)
        hidden_cases.make_instance("HH2", 8, 2)
        self.assertEqual(hidden_executor.prompt_pack_sha256(), before)
        self.assertEqual(len(before), 64)

    def test_instance_id_convention(self):
        from generators.seeds import parse_instance_id
        for family in FAMILIES:
            with self.subTest(family=family):
                inst = hidden_cases.make_instance(family, 99, 7)
                self.assertEqual(inst["instance_id"],
                                 "%s-hidden-00007" % family)
                self.assertEqual(inst["variant_class"], "hidden")
                fam, variant, index = parse_instance_id(inst["instance_id"])
                self.assertEqual((fam, variant, index), (family, "hidden", 7))


class TestHiddenRepoCleanliness(unittest.TestCase):
    def test_instances_never_written_to_repo(self):
        before = _snapshot_files(HIDDEN)
        for i in range(1, 6):
            for family in FAMILIES:
                hidden_cases.make_instance(family, 1000 + i, i)
        after = _snapshot_files(HIDDEN)
        self.assertEqual(before, after)


class TestHiddenGate(unittest.TestCase):
    def test_gate_refuses_without_scope(self):
        def chat(messages, **kw):
            raise AssertionError("model must not be called without scope")

        for bad_scope in (None, "", "public", "HIDDEN-OK"):
            with self.subTest(scope=bad_scope):
                with self.assertRaises(
                        hidden_executor.ScopeRequiredError):
                    hidden_executor.run_family(
                        "HH1", chat, run_id="RUN-H", model_id="stub",
                        trial_id=1, index=1, seed=1, scope=bad_scope)

    def test_gate_refuses_missing_scope_kwarg(self):
        def chat(messages, **kw):
            raise AssertionError("model must not be called without scope")

        with self.assertRaises(hidden_executor.ScopeRequiredError):
            hidden_executor.run_family("HH1", chat, run_id="RUN-H",
                                       model_id="stub")

    def test_gate_allows_hidden_ok(self):
        inst = hidden_cases.make_instance("HH1", 5, 1)
        answer = inst["oracle"]["value"]
        attempt, _resp = hidden_executor.run_family(
            "HH1", _stub_chat_factory(lambda _m: answer),
            run_id="RUN-H", model_id="stub", trial_id=1, index=1, seed=5,
            scope="hidden-ok")
        self.assertEqual(attempt["primary_status"], "PASS")
        self.assertEqual(attempt["variant_class"], "hidden")
        self.assertEqual(attempt["instance_id"], "HH1-hidden-00001")


class TestHiddenOracles(unittest.TestCase):
    def test_correct_reply_passes_all_families(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                inst = hidden_cases.make_instance(family, 31337, 2)
                ok, _log = hidden_cases.check_family(
                    family, inst["oracle"]["value"], inst)
                self.assertTrue(ok)

    def test_wrong_reply_fails(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                inst = hidden_cases.make_instance(family, 31337, 2)
                wrong = str(int(inst["oracle"]["value"]) + 1)
                ok, _log = hidden_cases.check_family(family, wrong, inst)
                self.assertFalse(ok)

    def test_executor_fail_produces_valid_attempt(self):
        from shared import schemas as _schemas
        attempt, _resp = hidden_executor.run_family(
            "HH2", _stub_chat_factory(lambda _m: "not a number"),
            run_id="RUN-H", model_id="stub", trial_id=1, index=1, seed=9,
            scope="hidden-ok")
        self.assertEqual(attempt["primary_status"], "FAIL")
        _schemas.validate_attempt(attempt)


if __name__ == "__main__":
    unittest.main()
