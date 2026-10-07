"""Agent-loop scenarios: shop frozen + ledger family (review P1-10)."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
for _p in (ROOT, SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import invariants  # noqa: E402
import runner  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


EPISODE = _load("agent_episode_scenarios", os.path.join(ROOT, "suites", "agent-loop", "episode.py"))


class ScenarioRegistryTests(unittest.TestCase):
    def test_shop_frozen_aliases(self):
        sc = EPISODE.SCENARIOS["shop"]
        self.assertIs(sc["system"], EPISODE.AGENT_SYSTEM)
        self.assertIs(sc["task"], EPISODE.AGENT_TASK)
        self.assertIs(sc["intended"], EPISODE.INTENDED)
        self.assertEqual(sc["family_id"], "AG")

    def test_unknown_scenario_fails_closed(self):
        with self.assertRaises(ValueError):
            EPISODE.scenario_for("nope")
        with self.assertRaises(ValueError):
            EPISODE.run_episode(lambda *a, **k: ("", 0, 0), scenario="nope")

    def test_families_map(self):
        self.assertEqual(EPISODE.SCENARIO_FAMILIES, {"AG": "shop", "AG2": "ledger"})


class LedgerOracleTests(unittest.TestCase):
    def test_bug_live_then_fixed(self):
        root = tempfile.mkdtemp(prefix="ledger_")
        try:
            EPISODE.build_ledger_repo(root)
            before = subprocess.run(
                ["python3", "-m", "pytest", "ledger/tests/", "-q"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertNotEqual(before.returncode, 0)
            path = os.path.join(root, "ledger", "paginate.py")
            src = open(path).read()
            self.assertIn("start + 1:start + size + 1", src)
            open(path, "w").write(src.replace("start + 1:start + size + 1", "start:start + size"))
            after = subprocess.run(
                ["python3", "-m", "pytest", "ledger/tests/", "-q"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(after.returncode, 0, after.stdout[-500:])
        finally:
            shutil.rmtree(root, ignore_errors=True)


class ScenarioAttemptTests(unittest.TestCase):
    def _result(self, **over):
        rec = {
            "trace": [
                {"step": 1, "tool": "read"},
                {"step": 2, "tool": "edit"},
                {"step": 3, "tool": "run"},
            ],
            "files_read": ["ledger/paginate.py"],
            "files_edited": ["ledger/paginate.py"],
            "diff_files": ["ledger/paginate.py"],
            "failed_calls": 0,
            "tests_green": True,
            "tool_calls": 3,
            "ran_tests_n": 2,
            "forbidden_touched": [],
            "hallucinated_paths": 0,
            "success": True,
            "terminal_state": {
                "terminal_state": "CLEAN_STOP",
                "verified": True,
                "pending_actions": 0,
                "forbidden_edits": 0,
            },
        }
        rec.update(over)
        return rec

    def test_ledger_a_metrics(self):
        a = EPISODE.score_a1_a15(self._result(), None, "ledger")
        for key in (
            "A1_recon_before_edit",
            "A3_intended_file",
            "A9_tests_green",
            "A12_diff_clean",
            "A13_efficient",
            "A14_stop_cleanly",
            "A15_success",
        ):
            self.assertTrue(a[key], key)

    def test_attempt_ids_per_scenario(self):
        shop = EPISODE.episode_attempt(self._result(), "r", "m", scenario="shop")
        led = EPISODE.episode_attempt(self._result(), "r", "m", scenario="ledger")
        self.assertEqual(
            (shop["task_family_id"], shop["instance_id"]), ("AG", "AG-canonical-00001")
        )
        self.assertEqual(
            (led["task_family_id"], led["instance_id"]), ("AG2", "AG2-canonical-00001")
        )
        self.assertEqual(led["scenario"], "ledger")

    def test_runner_smoke_both_families(self):
        out = "/tmp/emox_agent_scen"
        shutil.rmtree(out, ignore_errors=True)
        for family in ("AG", "AG2"):
            rundir, _ = runner.run_suite(
                "agent-loop",
                runner.stub_chat_factory("scen-test"),
                "m",
                "stub",
                0,
                1,
                1,
                0.25,
                out,
                families=[family],
            )
            events = [json.loads(line) for line in open(os.path.join(rundir, "events.jsonl"))]
            self.assertTrue(events)
            invariants.validate_run_semantics(events)
            self.assertEqual(events[0]["task_family_id"], family)


if __name__ == "__main__":
    unittest.main()
