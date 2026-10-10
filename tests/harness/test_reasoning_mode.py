"""Tests for Y-5 think plumbing (SPEC 37). Stdlib unittest, no network.

Covers:
  1. reasoning_mode_for() mapping table (all 4 branches).
  2. Attempt records carry a valid mode computed from the actual chat
     kwargs: code25 H3 -> "disabled", agent-loop -> "enabled",
     dynamic-code -> "provider_default" (stub chats only).

Field validation itself is owned by Y-1 (shared/schemas.py); these tests
only assert that Y-5 PRODUCES values in the closed SPEC 37 vocabulary.
"""

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

from backends import reasoning_mode_for  # noqa: E402
from schemas import VALID_REASONING_MODES  # noqa: E402 (Y-1 closed vocab, single source)

MODES = VALID_REASONING_MODES


def _load(name, path):
    """Load a suite module under a unique name (avoids basename clashes,
    e.g. the two suites' cases.py / executor.py files)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


CODE25 = _load("code25_executor_y5", os.path.join(ROOT, "suites", "code-bench-25", "executor.py"))
EPISODE = _load("agent_episode_y5", os.path.join(ROOT, "suites", "agent-loop", "episode.py"))
DYNAMIC = _load("dynamic_cases_y5", os.path.join(ROOT, "suites", "dynamic-code", "cases.py"))


def _stub_recorder(reply):
    """A chat stub recording the kwargs it was called with (no network)."""
    seen = {}

    def chat(messages, temp=0.4, think=None, num_predict=None):
        seen["think"] = think
        seen["num_predict"] = num_predict
        return reply, 0.1, {}

    chat.seen = seen
    return chat


class TestReasoningModeFor(unittest.TestCase):
    def test_enabled(self):
        self.assertEqual(reasoning_mode_for(True), "enabled")
        self.assertEqual(reasoning_mode_for(True, 600), "enabled")
        self.assertEqual(reasoning_mode_for(True, None, True), "enabled")

    def test_disabled(self):
        self.assertEqual(reasoning_mode_for(False), "disabled")
        self.assertEqual(reasoning_mode_for(False, 600), "disabled")
        self.assertEqual(reasoning_mode_for(False, None, True), "disabled")

    def test_native(self):
        # native transport without a think flag
        self.assertEqual(reasoning_mode_for(None, 600), "native")
        self.assertEqual(reasoning_mode_for(None, None, True), "native")
        self.assertEqual(reasoning_mode_for(None, 600, True), "native")

    def test_provider_default(self):
        # plain /v1 path: both None, not native
        self.assertEqual(reasoning_mode_for(), "provider_default")
        self.assertEqual(reasoning_mode_for(None, None), "provider_default")
        self.assertEqual(reasoning_mode_for(None, None, False), "provider_default")

    def test_closed_vocabulary(self):
        for mode in (
            reasoning_mode_for(True),
            reasoning_mode_for(False),
            reasoning_mode_for(None, 1),
            reasoning_mode_for(),
        ):
            self.assertIn(mode, MODES)


class TestAttemptModes(unittest.TestCase):
    def test_code25_h3_disabled(self):
        chat = _stub_recorder("the remainder is 4")
        attempt, _ = CODE25.run_family("H3", chat, run_id="R-Y5", model_id="m-y5")
        self.assertEqual(chat.seen["think"], False)  # actual chat kwarg
        self.assertEqual(attempt["reasoning_mode"], "disabled")
        self.assertIn(attempt["reasoning_mode"], MODES)
        self.assertEqual(attempt["primary_status"], "PASS")

    def test_code25_plain_family_provider_default(self):
        chat = _stub_recorder("مرحبا بالعالم " * 20)
        attempt, _ = CODE25.run_family("T5", chat, run_id="R-Y5", model_id="m-y5")
        self.assertIsNone(chat.seen["think"])
        self.assertIsNone(chat.seen["num_predict"])
        self.assertEqual(attempt["reasoning_mode"], "provider_default")

    def test_code25_h3_dynamic_disabled(self):
        chat = _stub_recorder("answer 4")
        attempt, _ = CODE25.run_family(
            "H3", chat, run_id="R-Y5", model_id="m-y5", seed=7, variant="perturbed"
        )
        self.assertEqual(attempt["reasoning_mode"], "disabled")

    def test_agent_loop_enabled(self):
        chat = _stub_recorder("FINAL: fixed the VAT rate")
        result, _traj = EPISODE.run_episode(chat)
        self.assertEqual(chat.seen["think"], True)  # actual chat kwarg
        attempt = EPISODE.episode_attempt(result, "R-Y5", "m-y5")
        self.assertEqual(attempt["reasoning_mode"], "enabled")
        self.assertIn(attempt["reasoning_mode"], MODES)

    def test_dynamic_provider_default(self):
        chat = _stub_recorder("0")
        attempt, _resp = DYNAMIC.run_family("DC1", chat, run_id="R-Y5", model_id="m-y5", seed=7)
        self.assertEqual(attempt["reasoning_mode"], "provider_default")
        self.assertIn(attempt["reasoning_mode"], MODES)


if __name__ == "__main__":
    unittest.main()
