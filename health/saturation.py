"""Saturation + novelty health (X-5, WP11). SPEC sections 11-12.

Contract refs: DEN C48 (retention is ratio-of-sums), C49 (gap is mean of
per-task gaps), C71 (saturation NA when <3 reference models), SPEC B49
(saturation penalty), SPEC 11 (SATURATED policy).

Formulas are imported from shared.scoring (novelty_retention_benchmark,
novelty_gap_benchmark, saturation_penalty); only the reference-population
gating + SATURATED policy live here.
"""

try:
    from scoring import novelty_retention_benchmark, novelty_gap_benchmark, saturation_penalty
except ImportError:  # package-style import (repo root on sys.path)
    from shared.scoring import (
        novelty_retention_benchmark,
        novelty_gap_benchmark,
        saturation_penalty,
    )

SATURATED_PASS_THRESHOLD = 0.98
SATURATED_DISCRIMINATION_THRESHOLD = 0.10

__all__ = ["saturation_snapshot", "SATURATED_PASS_THRESHOLD", "SATURATED_DISCRIMINATION_THRESHOLD"]


def mean_pass_rate(ref_scores):
    """Mean pass rate over reference models with valid scores. DEN C71."""
    vals = [s for s in ref_scores if s is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def saturation_snapshot(ref_scores, discrimination=None, tau=0.95):
    """Saturation snapshot for one task. DEN C71 / SPEC B49 / SPEC 11.

    ref_scores: per-reference-model pass rates (None = no valid score).
    Returns dict with mean_pass, n_ref, penalty (None when n_ref < 3),
    saturated bool, reason. NA is None, never 0.
    """
    valid = [s for s in ref_scores if s is not None]
    n_ref = len(valid)
    mean = mean_pass_rate(ref_scores)
    if n_ref < 3:  # C71: reference set too small => NA
        return {
            "mean_pass": mean,
            "n_ref": n_ref,
            "penalty": None,
            "saturated": False,
            "reason": "NA: fewer than 3 reference models (C71)",
        }
    penalty = saturation_penalty(mean, tau=tau)
    saturated = bool(
        mean is not None
        and mean > SATURATED_PASS_THRESHOLD
        and (discrimination is None or discrimination < SATURATED_DISCRIMINATION_THRESHOLD)
    )
    return {
        "mean_pass": mean,
        "n_ref": n_ref,
        "penalty": penalty,
        "saturated": saturated,
        "reason": "SATURATED (SPEC 11)" if saturated else "not saturated",
    }


def novelty_snapshot(canonical_by_task, novel_by_task):
    """Benchmark novelty health via DEN C48/C49 (delegates to scoring)."""
    tasks = sorted(set(canonical_by_task) & set(novel_by_task))
    pairs = [(canonical_by_task[t], novel_by_task[t]) for t in tasks]
    return {
        "retention": novelty_retention_benchmark(pairs),  # C48 ratio-of-sums
        "gap": novelty_gap_benchmark(pairs),  # C49 mean of gaps
        "n_tasks": len(pairs),
    }
