"""Flakiness + harness-validity health (X-5, WP11). DEN C69 / SPEC B48+B51.

DEN C69: flakiness is computed on VALID trials only —
D_flaky = N_valid_trials (ERROR/VOID excluded, never counted as passes).
Harness validity: 1 - infra_failures / all_attempted.
"""

try:
    from scoring import flakiness as _flakiness, harness_validity
except ImportError:  # package-style import (repo root on sys.path)
    from shared.scoring import flakiness as _flakiness, harness_validity

try:
    from schemas import SCORED_STATUSES
except ImportError:  # package-style import (repo root on sys.path)
    from shared.schemas import SCORED_STATUSES

__all__ = ["flakiness_snapshot", "validity_snapshot"]


def _valid_trials(trial_statuses):
    """Keep trials with a scored status; ERROR/VOID are not trials. C69."""
    return [s for s in trial_statuses if s in SCORED_STATUSES]


def flakiness_snapshot(trial_statuses):
    """Flakiness snapshot over valid trials only. B48/C69.

    trial_statuses: primary status per repeated trial of one task.
    Returns dict with p, flakiness, n_valid, n_total, reason.
    No valid trials => flakiness NA (None), never 0.
    """
    total = len(list(trial_statuses))
    valid = _valid_trials(trial_statuses)
    n_valid = len(valid)
    if n_valid == 0:
        return {
            "p": None,
            "flakiness": None,
            "n_valid": 0,
            "n_total": total,
            "reason": "NA: no valid trials (C69)",
        }
    passes = sum(1 for s in valid if s == "PASS")
    p = passes / n_valid
    return {
        "p": p,
        "flakiness": _flakiness(p),
        "n_valid": n_valid,
        "n_total": total,
        "reason": "ok",
    }


def validity_snapshot(n_infra_failures, n_attempted):
    """Harness-validity snapshot. B51/C69. None when nothing attempted."""
    value = harness_validity(n_infra_failures, n_attempted)
    if value is None:
        return {"validity": None, "reason": "NA: no attempts (C69)"}
    return {"validity": value, "reason": "ok"}
