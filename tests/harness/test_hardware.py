"""Hardware recording + two efficiency tiers (F-1, SPEC B28/32).

Covers: collect_environment() hardware object (all 5 keys non-empty,
unknown-tolerant), device_class string, manifest hardware field, the
Tier-A/Tier-B split in report_v2 (EfficiencyScore is Tier-A-only),
cross-device Tier-B comparisons labeled CONDITIONALLY_COMPARABLE, and
the absence of any blended single number mixing tiers. Stdlib only.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import report_v2
import runner
import schemas

HARDWARE_KEYS = ("cpu", "cpu_count", "ram_gb", "gpu", "device_class")

TIER_A_KEYS = ("tokens_per_solve", "calls_per_solve")

TIER_B_KEYS = ("latency_per_solve", "cost_per_solve", "device_class")


def attempt(status, score, **kw):
    """Schema-valid attempt with efficiency eligibility."""
    base = {
        "run_id": "RUN-HW",
        "model_id": "m",
        "task_family_id": "T",
        "instance_id": "i-%s" % kw.get("tag", "1"),
        "variant_class": "canonical",
        "trial_id": 1,
        "primary_status": status,
        "score": score,
        "primary_failure": None if status == "PASS" else "WRONG_RESULT",
    }
    base.update(kw)
    base.pop("tag", None)
    return schemas.validate_attempt(base)


class TestHardwareObject(unittest.TestCase):
    def test_hardware_present_with_all_keys_non_empty(self):
        env = runner.collect_environment()  # must never raise
        self.assertIn("hardware", env)
        hardware = env["hardware"]
        for key in HARDWARE_KEYS:
            self.assertIn(key, hardware, "hardware missing: %s" % key)
            self.assertIsInstance(hardware[key], str, key)
            self.assertTrue(hardware[key].strip(), "hardware.%s must never be empty" % key)

    def test_device_class_is_string(self):
        env = runner.collect_environment()
        device = env["hardware"]["device_class"]
        self.assertIsInstance(device, str)
        self.assertTrue(device.strip())

    def test_manifest_carries_hardware_device_class(self):
        manifest = runner.build_manifest(
            "code25", "a" * 64, "b" * 64, "stub-model", "stub", 0, 1, runner.make_run_id("RUN-hw")
        )
        self.assertIn("hardware", manifest)
        self.assertIsInstance(manifest["hardware"], str)
        self.assertTrue(manifest["hardware"].strip())
        schemas.validate_run_manifest(manifest)


class TestEfficiencyTiers(unittest.TestCase):
    def test_tier_split_present_in_report(self):
        events = [
            attempt("PASS", 1.0, tokens=100, tool_calls=4, latency=2.0, cost=0.1, tag="a"),
            attempt("FAIL", 0.0, tokens=50, tool_calls=2, latency=1.0, cost=0.05, tag="b"),
        ]
        rep = report_v2.build_v2_report(events, [], model_id="m", device_class="laptop-arm64-8gb")
        eff = rep["efficiency"]
        self.assertIn("tier_a", eff)
        self.assertIn("tier_b", eff)
        for key in TIER_A_KEYS:
            self.assertIn(key, eff["tier_a"])
        for key in TIER_B_KEYS:
            self.assertIn(key, eff["tier_b"])
        self.assertAlmostEqual(eff["tier_a"]["tokens_per_solve"], 150.0)
        self.assertAlmostEqual(eff["tier_a"]["calls_per_solve"], 6.0)
        self.assertAlmostEqual(eff["tier_b"]["latency_per_solve"], 3.0)
        self.assertAlmostEqual(eff["tier_b"]["cost_per_solve"], 0.15)
        self.assertEqual(eff["tier_b"]["device_class"], "laptop-arm64-8gb")

    def test_cross_device_comparison_is_conditional(self):
        verdict, reason = report_v2.efficiency_comparability("laptop-arm64-8gb", "laptop-x64-32gb")
        self.assertEqual(verdict, "CONDITIONALLY_COMPARABLE")
        self.assertTrue(reason)
        same, _ = report_v2.efficiency_comparability("laptop-arm64-8gb", "laptop-arm64-8gb")
        self.assertEqual(same, "COMPARABLE")
        unk, _ = report_v2.efficiency_comparability("unknown", "laptop-arm64-8gb")
        self.assertEqual(unk, "CONDITIONALLY_COMPARABLE")

    def test_no_blended_number_mixing_tiers(self):
        events = [
            attempt("PASS", 1.0, tokens=100, tool_calls=4, latency=2.0, cost=0.1, tag="a"),
            attempt("FAIL", 0.0, tokens=50, tool_calls=2, latency=1.0, cost=0.05, tag="b"),
        ]
        eff = report_v2.efficiency_tiers_report(
            events,
            device_class="laptop-arm64-8gb",
            budgets={"tokens": 1000, "calls": 40, "latency": 60, "cost": 5.0},
        )
        tier_a, tier_b = eff["tier_a"], eff["tier_b"]
        # A blended scalar would have to live at the top level of the
        # efficiency section, outside both tier blocks.
        top_scalars = [
            v
            for k, v in eff.items()
            if k not in ("tier_a", "tier_b") and isinstance(v, (int, float))
        ]
        self.assertEqual(top_scalars, [])
        # EfficiencyScore is Tier-A-only: latency/cost budgets cannot
        # move it (Tier-B resources never enter).
        no_b = report_v2.efficiency_tiers_report(
            events, device_class="laptop-arm64-8gb", budgets={"tokens": 1000, "calls": 40}
        )
        self.assertEqual(tier_a["efficiency_score"], no_b["tier_a"]["efficiency_score"])
        self.assertIsNotNone(tier_a["efficiency_score"])
        # Tier-B verdicts never silently merge: different classes of
        # synthetic reports stay conditional.
        verdict, _ = report_v2.efficiency_comparability(tier_b["device_class"], "cloud-gpu-a100")
        self.assertEqual(verdict, "CONDITIONALLY_COMPARABLE")


if __name__ == "__main__":
    unittest.main()
