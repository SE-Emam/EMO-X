"""Contamination-risk + calibration-eligibility health (X-5, WP11).

Contract refs: SPEC section 38 (public/private separation, dynamic seeds
preferred; hardcoded solutions must not durably pass), DEN C48/C49
(novelty inputs), DEN C50-C53 (calibration/abstention denominators).

Two concerns live here because both answer "can we still trust this
signal":
  1. contamination risk: high canonical success with collapsing novelty
     retention, or verbatim prompt/instance-hash overlap with public
     material, raises risk (never a model penalty by itself).
  2. calibration eligibility: thin wrappers over shared.scoring that
     expose the D_cal denominator explicitly (VOID/ERROR, missing
     confidence, or unresolved outcomes excluded per C50).
"""

try:
    from scoring import (brier_score, expected_calibration_error,
                         calibration_score, abstention_metrics,
                         novelty_retention_benchmark)
except ImportError:  # package-style import (repo root on sys.path)
    from shared.scoring import (brier_score, expected_calibration_error,
                                calibration_score, abstention_metrics,
                                novelty_retention_benchmark)

__all__ = ["contamination_snapshot", "calibration_eligibility_snapshot",
           "hash_overlap_rate"]


def hash_overlap_rate(observed_hashes, public_hashes):
    """Fraction of observed instance hashes present in public material."""
    observed = list(observed_hashes)
    if not observed:
        return None
    public = set(public_hashes or [])
    return sum(1 for h in observed if h in public) / len(observed)


def contamination_snapshot(canonical_rate=None, novel_rate=None,
                           pairs=None, overlap_rate=None):
    """Contamination-risk snapshot. SPEC 38 + DEN C48/C49.

    Inputs: benchmark canonical/novel rates (or raw C/N pairs), plus an
    optional hash-overlap rate. Returns risk in [0,1] (None when no
    evidence), level (low/elevated/high), and reason. A risk signal
    flags the *benchmark task* for rotation — it is never silently
    converted into a model failure.
    """
    retention = None
    if pairs is not None:
        retention = novelty_retention_benchmark(list(pairs))
    elif canonical_rate is not None and novel_rate is not None \
            and canonical_rate > 0:
        retention = min(1.0, novel_rate / canonical_rate)
    signals = []
    if retention is not None and canonical_rate is not None \
            and canonical_rate > 0.8 and retention < 0.7:
        signals.append("high-canonical-low-retention")
    if overlap_rate is not None and overlap_rate > 0:
        signals.append("hash-overlap")
    if retention is None and overlap_rate is None:
        return {"risk": None, "level": "unknown",
                "retention": None, "overlap_rate": overlap_rate,
                "reason": "NA: no contamination evidence"}
    risk = 0.0
    if retention is not None:
        risk = max(risk, 1.0 - retention)
    if overlap_rate is not None:
        risk = max(risk, min(1.0, overlap_rate))
    level = "low" if risk < 0.3 else ("elevated" if risk < 0.7 else "high")
    return {"risk": risk, "level": level, "retention": retention,
            "overlap_rate": overlap_rate,
            "reason": ";".join(signals) if signals else "no risk signals"}


def calibration_eligibility_snapshot(cases):
    """Calibration eligibility + scores over D_cal only. DEN C50-C53.

    cases: dicts with confidence + outcome. Returns D_cal, Brier, ECE,
    calibration score, and abstention arms (each NA arm stays None when
    its own denominator is 0 per C53).
    """
    try:
        from scoring import _calibration_pairs
    except ImportError:
        from shared.scoring import _calibration_pairs
    pairs = _calibration_pairs(list(cases or []))
    d_cal = len(pairs)
    if d_cal == 0:
        return {"d_cal": 0, "brier": None, "ece": None,
                "calibration": None,
                "reason": "NA: D_cal=0 (C50)"}
    return {"d_cal": d_cal,
            "brier": brier_score(cases),
            "ece": expected_calibration_error(cases),
            "calibration": calibration_score(cases),
            "reason": "ok"}


def abstention_snapshot(n_answered, correct_answers, n_abstained,
                        correct_abstentions):
    """Abstention arms with per-arm NA denominators. DEN C53."""
    return abstention_metrics(n_answered, correct_answers, n_abstained,
                              correct_abstentions)


def canary_check(text):
    """Detect hidden-prompt canary regurgitation (contamination proof).

    Returns True iff the digit-free hidden canary tag appears in model
    output: the tag exists ONLY in runtime hidden prompts (never stored,
    never published), so its presence in a reply proves the model saw
    leaked hidden material. Same tag as hidden suite prompts
    (shared.constants.CANARY_HIDDEN, single source).
    """
    try:
        from constants import CANARY_HIDDEN
    except ImportError:
        from shared.constants import CANARY_HIDDEN
    return CANARY_HIDDEN in (text or "")
