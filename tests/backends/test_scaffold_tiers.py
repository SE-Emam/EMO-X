"""Frozen scaffold tiers L0/L1/L2 (SPEC 27). Stdlib unittest, no network.

Covers: L0 chat-only (immediate FINAL stops with zero tool calls;
tool-shaped reply fails FORMAT_ERROR); L1 read/run accepted, ls/edit
rejected through the unknown-tool path; L2 default unchanged; invalid
scaffold raises ValueError; scaffold_level on results, trace entries,
and attempts; SG/SG_L1 plus relatives from synthetic tier scores via
scoring.scaffold_gain; tier mismatch gives NON_COMPARABLE;
build_v2_report carries the SG section; frozen prompts byte-identical.
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

import schemas  # noqa: E402
import scoring  # noqa: E402
import report_v2  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


EPISODE = _load("agent_episode_scaffold", os.path.join(ROOT, "suites", "agent-loop", "episode.py"))
LEGACY = _load("legacy_run_scaffold", os.path.join(SHARED, "run.py"))


def _close(tag):
    # Closing tags built by concatenation (never a literal in source).
    return "</" + tag + ">"


def _mkcall(fn, params):
    inner = "".join("<parameter=" + k + ">" + v + _close("parameter") for k, v in params)
    return (
        "<tool_call>\n<function="
        + fn
        + ">\n"
        + inner
        + _close("function")
        + "\n"
        + _close("tool_call")
    )


def _chat_script(replies):
    """Stub chat replaying replies in order (last repeats). No network."""
    calls = []

    def chat(history, **kwargs):
        calls.append(dict(kwargs))
        idx = min(len(calls) - 1, len(replies) - 1)
        return replies[idx], 0.05, 0

    chat.calls = calls
    return chat


READ_TAXES = _mkcall("read", (("path", "shop/taxes.py"),))
LS_REPO = _mkcall("ls", (("path", "."),))
CAT_TAXES = _mkcall("run", (("cmd", "cat shop/taxes.py"),))
EDIT_TAXES = _mkcall(
    "edit", (("path", "shop/taxes.py"), ("old", "    return 0.0"), ("new", "    return 0.20"))
)
RUN_TESTS = _mkcall("run", (("cmd", "python3 -m pytest shop/tests/ -q"),))
BOGUS = _mkcall("nope", (("path", "."),))
FINAL = "FINAL: done"


class TestPromptsFrozen(unittest.TestCase):
    def test_prompts_byte_identical_to_legacy(self):
        self.assertEqual(EPISODE.AGENT_SYSTEM, LEGACY.AGENT_SYSTEM)
        self.assertEqual(EPISODE.AGENT_TASK, LEGACY.AGENT_TASK)

    def test_tier_tool_tables_match_spec27(self):
        self.assertEqual(EPISODE.SCAFFOLD_TOOLS["L0-raw"], ())
        self.assertEqual(sorted(EPISODE.SCAFFOLD_TOOLS["L1-minimal"]), ["read", "run"])
        self.assertEqual(
            sorted(EPISODE.SCAFFOLD_TOOLS["L2-standard"]), ["edit", "ls", "read", "run"]
        )
        for level, tools in EPISODE.SCAFFOLD_TOOLS.items():
            self.assertEqual(sorted(tools), sorted(report_v2.SCAFFOLD_TIER_TOOLS[level]))


class TestL0Raw(unittest.TestCase):
    def test_final_immediately_zero_tool_calls(self):
        result, _traj = EPISODE.run_episode(_chat_script([FINAL]), max_steps=3, scaffold="L0-raw")
        self.assertEqual(result["tool_calls"], 0)
        self.assertTrue(result["stopped_cleanly"])
        self.assertEqual(result["scaffold_level"], "L0-raw")
        self.assertEqual(result["files_read"], [])
        self.assertEqual(result["files_edited"], [])

    def test_tool_shaped_reply_fails_format_error(self):
        result, traj = EPISODE.run_episode(
            _chat_script([READ_TAXES, FINAL]), max_steps=3, scaffold="L0-raw"
        )
        self.assertEqual(result["tool_calls"], 0)
        self.assertEqual(result["files_read"], [])
        kinds = [f["kind"] for f in traj["failures"]]
        self.assertIn("FORMAT_ERROR", kinds)
        self.assertGreaterEqual(result["failed_calls"], 1)
        # FINAL still stops the episode.
        self.assertTrue(result["stopped_cleanly"])


class TestL1Minimal(unittest.TestCase):
    def test_read_accepted(self):
        result, traj = EPISODE.run_episode(
            _chat_script([READ_TAXES, FINAL]), max_steps=3, scaffold="L1-minimal"
        )
        self.assertIn("shop/taxes.py", result["files_read"])
        self.assertEqual(result["scaffold_level"], "L1-minimal")
        self.assertTrue(any(o["tool"] == "read" and o["ok"] for o in traj["observations"]))

    def test_run_accepted(self):
        _result, traj = EPISODE.run_episode(
            _chat_script([CAT_TAXES, FINAL]), max_steps=3, scaffold="L1-minimal"
        )
        self.assertTrue(any(o["tool"] == "run" and o["ok"] for o in traj["observations"]))

    def test_ls_rejected_via_unknown_tool_path(self):
        result, traj = EPISODE.run_episode(
            _chat_script([LS_REPO, FINAL]), max_steps=3, scaffold="L1-minimal"
        )
        bad = [o for o in traj["observations"] if o["tool"] == "ls"]
        self.assertTrue(bad)
        self.assertTrue(all(not o["ok"] for o in bad))
        self.assertTrue(all("unknown tool ls" in o["output"] for o in bad))
        self.assertGreaterEqual(result["failed_calls"], 1)

    def test_edit_rejected_via_unknown_tool_path(self):
        result, traj = EPISODE.run_episode(
            _chat_script([EDIT_TAXES, FINAL]), max_steps=3, scaffold="L1-minimal"
        )
        self.assertEqual(result["files_edited"], [])
        bad = [o for o in traj["observations"] if o["tool"] == "edit"]
        self.assertTrue(bad)
        self.assertTrue(all("unknown tool edit" in o["output"] for o in bad))


class TestL2Standard(unittest.TestCase):
    def test_default_is_l2_standard(self):
        result, _traj = EPISODE.run_episode(_chat_script([FINAL]), max_steps=2)
        self.assertEqual(result["scaffold_level"], "L2-standard")

    def test_full_loop_repairs_and_tags_attempt(self):
        result, _traj = EPISODE.run_episode(
            _chat_script([READ_TAXES, EDIT_TAXES, RUN_TESTS, FINAL]),
            max_steps=6,
            scaffold="L2-standard",
        )
        self.assertIn("shop/taxes.py", result["files_edited"])
        self.assertTrue(result["tests_green"])
        self.assertTrue(result["success"])
        attempt = EPISODE.episode_attempt(result, run_id="RUN-SG", model_id="m")
        self.assertEqual(attempt["scaffold_level"], "L2-standard")
        schemas.validate_attempt(attempt)

    def test_unknown_tool_still_rejected(self):
        _result, traj = EPISODE.run_episode(
            _chat_script([BOGUS, FINAL]), max_steps=3, scaffold="L2-standard"
        )
        bad = [o for o in traj["observations"] if o["tool"] == "nope"]
        self.assertTrue(bad)
        self.assertTrue(all("unknown tool nope" in o["output"] for o in bad))


class TestInvalidScaffold(unittest.TestCase):
    def test_unknown_tier_raises_value_error(self):
        with self.assertRaises(ValueError):
            EPISODE.run_episode(_chat_script([FINAL]), scaffold="L9-ultra")


class TestScaffoldLevelThreading(unittest.TestCase):
    def test_tool_trace_entries_tagged(self):
        for level in ("L1-minimal", "L2-standard"):
            result, _traj = EPISODE.run_episode(
                _chat_script([READ_TAXES, FINAL]), max_steps=3, scaffold=level
            )
            tools = [t for t in result["trace"] if "tool" in t]
            self.assertTrue(tools)
            for entry in tools:
                self.assertEqual(entry.get("scaffold_level"), level)

    def test_attempt_flows_through_schema(self):
        result, _traj = EPISODE.run_episode(_chat_script([FINAL]), max_steps=2, scaffold="L0-raw")
        attempt = EPISODE.episode_attempt(result, "RUN-SG", "m")
        self.assertEqual(attempt["scaffold_level"], "L0-raw")
        # Runner path preserves unknown attempt fields (no runner edit).
        kept = schemas.validate_attempt(dict(attempt))
        self.assertEqual(kept["scaffold_level"], "L0-raw")

    def test_explicit_override_and_legacy_default(self):
        result, _traj = EPISODE.run_episode(_chat_script([FINAL]), max_steps=2)
        attempt = EPISODE.episode_attempt(result, "RUN-SG", "m", scaffold_level="L1-minimal")
        self.assertEqual(attempt["scaffold_level"], "L1-minimal")
        legacy = dict(result)
        del legacy["scaffold_level"]
        attempt2 = EPISODE.episode_attempt(legacy, "RUN-SG", "m")
        self.assertEqual(attempt2["scaffold_level"], "L2-standard")


class TestScaffoldGainReport(unittest.TestCase):
    TIERS = {"L0-raw": 0.2, "L1-minimal": 0.5, "L2-standard": 0.8}

    def test_four_numbers_on_synthetic_tiers(self):
        rep = report_v2.scaffold_gain_report(dict(self.TIERS))
        self.assertAlmostEqual(rep["SG"], 0.6)
        self.assertAlmostEqual(rep["SG_relative"], 3.0)
        self.assertAlmostEqual(rep["SG_L1"], 0.3)
        self.assertAlmostEqual(rep["SG_L1_relative"], 1.5)

    def test_reuses_scoring_scaffold_gain(self):
        rep = report_v2.scaffold_gain_report(dict(self.TIERS))
        sg = scoring.scaffold_gain(0.2, 0.8)
        sg1 = scoring.scaffold_gain(0.2, 0.5)
        self.assertAlmostEqual(rep["SG"], sg["absolute"])
        self.assertAlmostEqual(rep["SG_relative"], sg["relative"])
        self.assertAlmostEqual(rep["SG_L1"], sg1["absolute"])
        self.assertAlmostEqual(rep["SG_L1_relative"], sg1["relative"])

    def test_missing_tiers_are_na(self):
        rep = report_v2.scaffold_gain_report(None)
        self.assertIsNone(rep["SG"])
        self.assertIsNone(rep["SG_relative"])
        self.assertIsNone(rep["SG_L1"])
        self.assertIsNone(rep["SG_L1_relative"])
        partial = report_v2.scaffold_gain_report({"L0-raw": 0.4, "L2-standard": 0.9})
        self.assertAlmostEqual(partial["SG"], 0.5)
        self.assertIsNone(partial["SG_L1"])
        self.assertIsNone(partial["SG_L1_relative"])

    def test_build_v2_report_carries_sg_section(self):
        rep = report_v2.build_v2_report([], [], model_id="m", tier_scores=dict(self.TIERS))
        sg = rep["scaffold_gain"]
        self.assertAlmostEqual(sg["SG"], 0.6)
        self.assertAlmostEqual(sg["SG_relative"], 3.0)
        self.assertAlmostEqual(sg["SG_L1"], 0.3)
        self.assertAlmostEqual(sg["SG_L1_relative"], 1.5)
        default = report_v2.build_v2_report([], [])
        self.assertIsNone(default["scaffold_gain"]["SG"])
        self.assertIsNone(default["scaffold_gain"]["SG_L1"])


class TestScaffoldComparability(unittest.TestCase):
    def test_matching_tiers_comparable(self):
        verdict, _reason = report_v2.scaffold_comparability(
            report_v2.SCAFFOLD_TIER_TOOLS, dict(report_v2.SCAFFOLD_TIER_TOOLS)
        )
        self.assertEqual(verdict, "COMPARABLE")

    def test_narrower_l1_is_non_comparable(self):
        other = dict(report_v2.SCAFFOLD_TIER_TOOLS)
        other["L1-minimal"] = ("read",)
        verdict, reason = report_v2.scaffold_comparability(report_v2.SCAFFOLD_TIER_TOOLS, other)
        self.assertEqual(verdict, "NON_COMPARABLE")
        self.assertIn("SPEC 27", reason)

    def test_manifest_form_mismatch(self):
        man_a = {"scaffold_tier_tools": dict(report_v2.SCAFFOLD_TIER_TOOLS)}
        tools_b = dict(report_v2.SCAFFOLD_TIER_TOOLS)
        tools_b["L1-minimal"] = ("read", "run", "ls")
        man_b = {"scaffold_tier_tools": tools_b}
        verdict, _reason = report_v2.scaffold_comparability(
            None, None, manifest_a=man_a, manifest_b=man_b
        )
        self.assertEqual(verdict, "NON_COMPARABLE")


if __name__ == "__main__":
    unittest.main()
