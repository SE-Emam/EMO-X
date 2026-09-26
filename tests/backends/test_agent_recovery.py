"""Canonical A7 recovery: fault + recorded recovery + verification."""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
for _p in (ROOT, SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


EPISODE = _load("agent_episode_recovery",
                os.path.join(ROOT, "suites", "agent-loop", "episode.py"))


def _result(**over):
    rec = {"trace": [], "files_read": [], "files_edited": [],
           "diff_files": [], "failed_calls": 0, "tests_green": False,
           "tool_calls": 0}
    rec.update(over)
    return rec


def _traj(failures=(), recoveries=()):
    return {"failures": list(failures), "recoveries": list(recoveries)}


class CanonicalRecoveryTests(unittest.TestCase):
    def test_fault_recovery_verified(self):
        a = EPISODE.score_a1_a15(
            _result(failed_calls=2, tests_green=True),
            _traj([{"step": 2, "kind": "WRONG_TOOL"}],
                  [{"step": 3, "after": "tool ok following failure"}]))
        self.assertTrue(a["A7_recovery"])

    def test_unverified_recovery_earns_nothing(self):
        a = EPISODE.score_a1_a15(
            _result(failed_calls=2, tests_green=False),
            _traj([{"step": 2, "kind": "WRONG_TOOL"}],
                  [{"step": 3, "after": "tool ok following failure"}]))
        self.assertFalse(a["A7_recovery"])

    def test_fault_free_episode_is_not_recovery(self):
        a = EPISODE.score_a1_a15(_result(tests_green=True), _traj())
        self.assertFalse(a["A7_recovery"])

    def test_green_without_recorded_recovery_is_not_recovery(self):
        a = EPISODE.score_a1_a15(
            _result(failed_calls=1, tests_green=True),
            _traj([{"step": 2, "kind": "FORMAT_ERROR"}], []))
        self.assertFalse(a["A7_recovery"])

    def test_backend_error_is_not_a_model_fault(self):
        a = EPISODE.score_a1_a15(
            _result(failed_calls=0, tests_green=True),
            _traj([{"step": 1, "kind": "BACKEND_ERROR"}],
                  [{"step": 2, "after": "tool ok following failure"}]))
        self.assertFalse(a["A7_recovery"])

    def test_legacy_path_without_trajectory(self):
        a = EPISODE.score_a1_a15(_result(tests_green=True))
        self.assertTrue(a["A7_recovery"])


if __name__ == "__main__":
    unittest.main()
