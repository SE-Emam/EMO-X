"""Scoring API contract tests (roadmap: contract tests).

Pins the public surface of shared/scoring.py so refactors cannot
silently drop/rename functions, add I/O dependencies, or break
determinism and NA conventions:

- every CONTRACTED function exists and is callable;
- stdlib-pure imports only (math/random/fractions/typing + sibling
  EMO modules — never urllib/socket/subprocess/requests/numpy);
- deterministic: identical inputs + seed give identical outputs;
- NA convention: D=0/empty input gives None, never 0 or an exception
  (except documented ValueError guards).
"""

import inspect
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import scoring

CONTRACTED = (
    "pass_rate", "family_balanced_pass_rate", "coverage",
    "generalization_score", "novelty_robustness",
    "novelty_retention_benchmark",
    "tool_precision", "tool_recall", "tool_f1", "argument_accuracy",
    "sequence_validity", "action_discipline", "side_effect_safety",
    "tool_discipline", "tool_components_from_agent_attempt",
    "tool_discipline_from_attempts",
    "recovery_rate", "recovery_score", "recovery_precision",
    "efficiency_score", "budget_compliance",
    "state_awareness", "stale_plan_rate", "correct_replanning_rate",
    "robustness_from_drift",
    "bootstrap_ci", "paired_bootstrap_diff", "instance_paired_bootstrap",
    "wilson_interval", "mde_paired", "usd_per_solve", "pareto_frontier",
    "passk_summary",
    "family_value_lists", "family_strict_lists", "instance_mean_scores",
    "aggregate_events", "time_horizon_fit",
    "calibration_score", "brier_score", "safety_score", "csv_rate",
    "saturation_penalty",
    "BOOTSTRAP_RESAMPLES", "BOOTSTRAP_MAX",
)


class ApiSurfaceTests(unittest.TestCase):
    def test_contracted_names_exist(self):
        missing = [n for n in CONTRACTED if not hasattr(scoring, n)]
        self.assertEqual(missing, [])

    def test_functions_callable_with_signatures(self):
        for name in CONTRACTED:
            obj = getattr(scoring, name)
            if isinstance(obj, (int, float)):
                continue
            self.assertTrue(callable(obj), name)
            self.assertTrue(inspect.signature(obj) is not None, name)


class PurityTests(unittest.TestCase):
    def test_no_io_or_network_imports(self):
        import scoring as _s
        mods = set(getattr(_s, "__dict__", {}).keys())
        src = inspect.getsource(_s)
        for banned in ("urllib", "socket", "subprocess", "requests",
                       "numpy", "open("):
            self.assertNotIn("import %s" % banned, src, banned)
        self.assertNotIn("urllib.request", src)


class DeterminismTests(unittest.TestCase):
    def test_bootstrap_deterministic(self):
        groups = [[1.0, 0.0], [0.5]]
        a = scoring.bootstrap_ci(groups, B=500, seed=3)
        b = scoring.bootstrap_ci(groups, B=500, seed=3)
        self.assertEqual(a, b)

    def test_paired_deterministic(self):
        ga, gb = {"t": [1.0, 0.0]}, {"t": [0.0, 0.0]}
        a = scoring.paired_bootstrap_diff(ga, gb, B=500, seed=3)
        b = scoring.paired_bootstrap_diff(ga, gb, B=500, seed=3)
        self.assertEqual(a, b)


class NaConventionTests(unittest.TestCase):
    def test_empty_gives_none(self):
        self.assertIsNone(scoring.bootstrap_ci([], B=100, seed=1)["mean"])
        self.assertIsNone(scoring.tool_discipline([]))
        self.assertIsNone(scoring.tool_discipline([None]))
        self.assertIsNone(scoring.recovery_rate([]))
        self.assertIsNone(scoring.pass_rate([]))


if __name__ == "__main__":
    unittest.main()
