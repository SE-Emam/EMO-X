"""EMO-X capability-profile assembly (thin layer over scoring).

Contract refs: SPEC B60 (required public result), B61 (profile, not one
number), B55/B57 (optional overall), B56/C75 (eligibility gate),
DEN C84 (no model names inspected).

This module contains NO single-number ranking display logic beyond
EMO_Overall for eligible models (B61): the canonical result is
capability profile + failure fingerprint + efficiency + uncertainty.
"""

try:
    from scoring import (
        emo_capability_score,
        emo_overall_score,
        safety_eligibility_gate,
        DEFAULT_CAPABILITY_WEIGHTS,
    )
except ImportError:
    from shared.scoring import (
        emo_capability_score,
        emo_overall_score,
        safety_eligibility_gate,
        DEFAULT_CAPABILITY_WEIGHTS,
    )

#: Required public result fields (SPEC B60).
REQUIRED_PROFILE_FIELDS = (
    "pass_rate",
    "partial_credit",
    "generalization",
    "tool_discipline",
    "recovery_rate",
    "efficiency",
    "calibration",
    "safety",
    "long_horizon",
    "human_minutes_solved",
    "failure_fingerprint",
    "ci_95",
    "coverage",
    "benchmark_health",
)


def assemble_capability_profile(
    dimensions,
    failure_fingerprint=None,
    efficiency=None,
    ci_95=None,
    coverage=None,
    benchmark_health=None,
    safety=None,
    csv_rate=None,
    weights=None,
):
    """Assemble the canonical capability profile. SPEC B60/B61.

    dimensions: {dim: value-or-None} capability dims.
    Returns dict with profile, eligibility, EMO_Overall (only when
    eligible, else None = NOT RANKABLE), fingerprint, efficiency,
    uncertainty, coverage, health. Never invents ranking order.
    """
    weights = weights or DEFAULT_CAPABILITY_WEIGHTS
    eligible = safety_eligibility_gate(
        0 if csv_rate is None else csv_rate, coverage, benchmark_health, dimensions, weights
    )
    # Gate needs explicit CSVRate; unknown CSV => ineligible (fail-closed).
    if csv_rate is None:
        eligible = False
    overall = emo_overall_score(
        dimensions, 0 if csv_rate is None else csv_rate, coverage, benchmark_health, weights
    )
    return {
        "capability_profile": dict(dimensions),
        "eligible": bool(eligible),
        "eligibility": ("ELIGIBLE" if eligible else "NOT RANKABLE"),
        "EMO_Overall": overall,
        "failure_fingerprint": dict(failure_fingerprint or {}),
        "efficiency": dict(efficiency or {}),
        "uncertainty_95": ci_95,
        "coverage": coverage,
        "benchmark_health": benchmark_health,
        "safety": safety,
        "csv_rate": csv_rate,
    }


def profile_completeness(dimensions, weights=None):
    """Fraction of required weight with defined dims. DEN C75."""
    from collections import OrderedDict  # Local standard-library import is intentional.

    weights = weights or DEFAULT_CAPABILITY_WEIGHTS
    try:
        from scoring import REQUIRED_DIMENSIONS
    except ImportError:
        from shared.scoring import REQUIRED_DIMENSIONS
    req = [d for d in REQUIRED_DIMENSIONS if d in weights]
    total = sum(weights[d] for d in req)
    if total <= 0:
        return None
    have = sum(weights[d] for d in req if dimensions.get(d) is not None)
    return have / total
