"""Hierarchical gauntlet diagnosis (F-3, SPEC 28): causal order + anchoring.

Covers: GAUNTLET_CAUSAL_ORDER (mirrors the oracle DIMENSIONS order),
first_missed (earliest missed in causal order, None when all hit),
gauntlet_diagnosis verdicts (composition vs capability vs unanchored),
build_gauntlet_section wiring into build_v2_report, and oracle
invariance: the gauntlet oracle (cases.check_family + run_family
scoring, B58 prompt/harness hashes) stays byte-identical — pinned
hashes plus three fixed reply/stage combos asserting
attempt score == hits/total. Stdlib only; report-side only, the oracle
files under suites/gauntlet/ are never written here.
"""

import importlib.util
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import report_v2  # noqa: E402

#: Pinned oracle hashes recorded before the F-3 change (SPEC 28:
#: the gauntlet oracle must stay byte-identical; any edit to
#: suites/gauntlet/* invalidates these and fails closed here).
PINNED_PROMPT_PACK_SHA256 = "2fa41d20be69e646c2b59ff9a064324072ad982c58cc9aa3a6b41c29ee68f3c3"
PINNED_CASES_HARNESS_SHA256 = "11248d8366d606afb9b7d2ab0ce2e2c54f1500a34d5f5a7436cd32b744de1faf"
PINNED_EXECUTOR_HARNESS_SHA256 = "2543d0f0104a6ff27d649075a274a976f77662a252bce8a346e81bdc2c4d8399"

#: Fixed seed for the pinned episode combos (deterministic generator).
PIN_SEED = 7

#: Reference scores used across verdict tests (SPEC 28 example shape):
#: passed standalone (>=0.5) vs failed standalone (<0.5).
PIN_REFERENCES = {
    "recovery-opportunity": 0.9,
    "tool-failure": 0.85,
    "state-change": 0.4,
    "stale-documentation": 0.9,
}


def _load_module(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _gauntlet_cases():
    # Basename isolation: load by file path, never bare ``import cases``
    # (every suite ships a cases.py; bare imports collide in sys.modules).
    return _load_module(
        "emox_gauntlet_cases", os.path.join(_ROOT, "suites", "gauntlet", "cases.py")
    )


def _gauntlet_executor():
    return _load_module(
        "emox_gauntlet_executor_diagtest", os.path.join(_ROOT, "suites", "gauntlet", "executor.py")
    )


def _all_hit():
    return {s: True for s in report_v2.GAUNTLET_CAUSAL_ORDER}


def _stub_chat(reply):
    def chat(messages):
        return reply, 0.1, {}

    return chat


class CausalOrderTests(unittest.TestCase):
    def test_order_constant(self):
        self.assertEqual(
            report_v2.GAUNTLET_CAUSAL_ORDER,
            (
                "ambiguous-requirement",
                "stale-documentation",
                "tool-failure",
                "state-change",
                "misleading-note",
                "hidden-edge-case",
                "test-failure",
                "recovery-opportunity",
                "final-verification",
            ),
        )

    def test_order_matches_oracle_dimensions(self):
        # Read-only cross-check: diagnosis order mirrors the oracle's
        # DIMENSIONS tuple (SPEC 28 causal chain); oracle untouched.
        self.assertEqual(tuple(_gauntlet_cases().DIMENSIONS), report_v2.GAUNTLET_CAUSAL_ORDER)

    def test_first_missed_miss_stages_3_and_7(self):
        # Hand-check: miss the 3rd (tool-failure) and 7th
        # (test-failure) stages => prime suspect is the 3rd.
        stages = _all_hit()
        stages["tool-failure"] = False
        stages["test-failure"] = False
        self.assertEqual(report_v2.first_missed(stages), "tool-failure")

    def test_first_missed_all_hit_is_none(self):
        self.assertIsNone(report_v2.first_missed(_all_hit()))

    def test_first_missed_ignores_unknown_keys(self):
        stages = _all_hit()
        stages["not-a-stage"] = False
        self.assertIsNone(report_v2.first_missed(stages))

    def test_first_missed_absent_key_counts_as_missed(self):
        stages = _all_hit()
        del stages["stale-documentation"]
        self.assertEqual(report_v2.first_missed(stages), "stale-documentation")


class ReferenceAnchoringTests(unittest.TestCase):
    def test_composition_verdict(self):
        # Missed in gauntlet, passed standalone (>=0.5) =
        # integration overload, not a capability gap (SPEC 28).
        stages = _all_hit()
        stages["tool-failure"] = False
        diag = report_v2.gauntlet_diagnosis(stages, PIN_REFERENCES)
        self.assertEqual(diag["first_missed"], "tool-failure")
        self.assertEqual(diag["missed"], ["tool-failure"])
        self.assertEqual(diag["verdicts"], {"tool-failure": "composition"})

    def test_capability_verdict(self):
        # Missed in both gauntlet and standalone (<0.5) (SPEC 28).
        stages = _all_hit()
        stages["state-change"] = False
        diag = report_v2.gauntlet_diagnosis(stages, PIN_REFERENCES)
        self.assertEqual(diag["verdicts"], {"state-change": "capability"})

    def test_unanchored_verdict(self):
        # No standalone reference for this dimension (SPEC 28).
        stages = _all_hit()
        stages["hidden-edge-case"] = False
        diag = report_v2.gauntlet_diagnosis(stages, PIN_REFERENCES)
        self.assertEqual(diag["verdicts"], {"hidden-edge-case": "unanchored"})

    def test_mixed_verdicts_causal_missed_order(self):
        stages = _all_hit()
        stages["tool-failure"] = False
        stages["state-change"] = False
        stages["hidden-edge-case"] = False
        diag = report_v2.gauntlet_diagnosis(stages, PIN_REFERENCES)
        self.assertEqual(diag["first_missed"], "tool-failure")
        self.assertEqual(diag["missed"], ["tool-failure", "state-change", "hidden-edge-case"])
        self.assertEqual(
            diag["verdicts"],
            {
                "tool-failure": "composition",
                "state-change": "capability",
                "hidden-edge-case": "unanchored",
            },
        )

    def test_threshold_boundary(self):
        stages = _all_hit()
        stages["tool-failure"] = False
        at = report_v2.gauntlet_diagnosis(stages, {"tool-failure": 0.5})
        self.assertEqual(at["verdicts"], {"tool-failure": "composition"})
        below = report_v2.gauntlet_diagnosis(stages, {"tool-failure": 0.4999})
        self.assertEqual(below["verdicts"], {"tool-failure": "capability"})

    def test_all_hit_empty_verdicts(self):
        diag = report_v2.gauntlet_diagnosis(_all_hit(), PIN_REFERENCES)
        self.assertIsNone(diag["first_missed"])
        self.assertEqual(diag["missed"], [])
        self.assertEqual(diag["verdicts"], {})


class GauntletSectionTests(unittest.TestCase):
    def test_section_single_episode(self):
        stages = _all_hit()
        stages["tool-failure"] = False
        stages["test-failure"] = False
        section = report_v2.build_gauntlet_section(
            stages, reference_scores={"tool-failure": 0.85, "test-failure": 0.4}
        )
        self.assertEqual(section["n_episodes"], 1)
        self.assertEqual(section["first_missed"], "tool-failure")
        self.assertEqual(section["missed"], ["tool-failure", "test-failure"])
        self.assertEqual(
            section["verdicts"], {"tool-failure": "composition", "test-failure": "capability"}
        )

    def test_section_aggregates_episodes_by_and(self):
        first, second = _all_hit(), _all_hit()
        first["tool-failure"] = False
        second["state-change"] = False
        section = report_v2.build_gauntlet_section(
            [first, second], reference_scores={"tool-failure": 0.85, "state-change": 0.4}
        )
        # Compound all-stages bar: a stage counts only when hit in
        # every observed episode (SPEC 28, no fragmentation).
        self.assertEqual(section["n_episodes"], 2)
        self.assertTrue(section["stages"]["ambiguous-requirement"])
        self.assertFalse(section["stages"]["tool-failure"])
        self.assertFalse(section["stages"]["state-change"])
        self.assertEqual(section["first_missed"], "tool-failure")

    def test_section_no_data_is_na(self):
        for empty in (None, [], [None]):
            section = report_v2.build_gauntlet_section(empty)
            self.assertEqual(section["n_episodes"], 0)
            self.assertIsNone(section["stages"])
            self.assertIsNone(section["first_missed"])
            self.assertEqual(section["missed"], [])
            self.assertEqual(section["verdicts"], {})

    def test_report_carries_gauntlet_section(self):
        stages = _all_hit()
        stages["tool-failure"] = False
        rep = report_v2.build_v2_report(
            [],
            [{"gauntlet_stages": stages}],
            model_id="m",
            gauntlet_reference_scores={"tool-failure": 0.85},
        )
        self.assertEqual(rep["gauntlet"]["first_missed"], "tool-failure")
        self.assertEqual(rep["gauntlet"]["verdicts"], {"tool-failure": "composition"})

    def test_report_default_is_na(self):
        rep = report_v2.build_v2_report([], [], model_id="m")
        self.assertEqual(rep["gauntlet"]["n_episodes"], 0)
        self.assertIsNone(rep["gauntlet"]["first_missed"])


class OracleInvarianceTests(unittest.TestCase):
    """Veto-level guard: B58 prompt/harness hashes pinned (SPEC 28)."""

    def test_prompt_pack_hash_unchanged(self):
        self.assertEqual(_gauntlet_cases().prompt_pack_sha256(), PINNED_PROMPT_PACK_SHA256)

    def test_cases_harness_hash_unchanged(self):
        self.assertEqual(_gauntlet_cases().harness_sha256(), PINNED_CASES_HARNESS_SHA256)

    def test_executor_harness_hash_unchanged(self):
        self.assertEqual(_gauntlet_executor().harness_sha256(), PINNED_EXECUTOR_HARNESS_SHA256)

    def test_pinned_full_pass_episode(self):
        # Combo 1/3: every marker present -> 9/9, PASS, score 1.0.
        cases = _gauntlet_cases()
        inst = cases.make_instance("GT1", PIN_SEED, 1)
        params, total = inst["parameters"], inst["oracle"]["total"]
        reply = (
            "ASSUME: base plus current delta. base %d delta %d. "
            "RETRY after TOOL_TIMEOUT. EMPTY: 0. "
            "FIXED: total=base+delta. VERIFY: total=%d confirmed."
            % (params["base"], params["delta"], total)
        )
        hits, total_stages, stages = cases.check_family("GT1", reply, inst)
        self.assertEqual((hits, total_stages), (9, 9))
        attempt, response = cases.run_family(
            "GT1", _stub_chat(reply), "RUN-G", "m", trial_id=1, index=1, seed=PIN_SEED
        )
        self.assertEqual(attempt["primary_status"], "PASS")
        self.assertEqual(attempt["score"], hits / total_stages)
        self.assertEqual(response["gauntlet_stages"], stages)
        self.assertIsNone(report_v2.first_missed(response["gauntlet_stages"]))

    def test_pinned_empty_reply_episode(self):
        # Combo 2/3: empty reply -> only the benign-note stage hits
        # (1/9), PARTIAL, score == hits/total.
        cases = _gauntlet_cases()
        inst = cases.make_instance("GT1", PIN_SEED, 1)
        hits, total_stages, stages = cases.check_family("GT1", "", inst)
        self.assertEqual((hits, total_stages), (1, 9))
        attempt, response = cases.run_family(
            "GT1", _stub_chat(""), "RUN-G", "m", trial_id=1, index=1, seed=PIN_SEED
        )
        self.assertEqual(attempt["primary_status"], "PARTIAL")
        self.assertEqual(attempt["score"], hits / total_stages)
        self.assertEqual(response["gauntlet_stages"], stages)
        # Wiring: the response stages feed the report diagnosis.
        rep = report_v2.build_v2_report(
            [], [response], model_id="m", gauntlet_reference_scores=dict(PIN_REFERENCES)
        )
        self.assertEqual(rep["gauntlet"]["n_episodes"], 1)
        self.assertEqual(rep["gauntlet"]["first_missed"], "ambiguous-requirement")

    def test_pinned_partial_episode(self):
        # Combo 3/3: misses stale-documentation + state-change only
        # (7/9), PARTIAL, score == hits/total.
        cases = _gauntlet_cases()
        inst = cases.make_instance("GT1", PIN_SEED, 1)
        reply = (
            "ASSUME: guess. RETRY. EMPTY: 0. FIXED: x. "
            "VERIFY: total=%d confirmed." % inst["oracle"]["total"]
        )
        hits, total_stages, stages = cases.check_family("GT1", reply, inst)
        self.assertEqual((hits, total_stages), (7, 9))
        self.assertEqual(
            sorted(k for k, v in stages.items() if not v), ["stale-documentation", "state-change"]
        )
        attempt, _ = cases.run_family(
            "GT1", _stub_chat(reply), "RUN-G", "m", trial_id=1, index=1, seed=PIN_SEED
        )
        self.assertEqual(attempt["primary_status"], "PARTIAL")
        self.assertEqual(attempt["score"], hits / total_stages)
        self.assertEqual(report_v2.first_missed(stages), "stale-documentation")


if __name__ == "__main__":
    unittest.main()
