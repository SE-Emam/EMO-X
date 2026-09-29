"""EMO-X shared numeric thresholds (stdlib only).

Contract refs: SPEC Part B (B49/B52/B55/B56), DEN Part C (C66/C72/C75).

Single-source pins for gates and defaults previously scattered as
literals across the scoring engine. scoring.BOOTSTRAP_RESAMPLES remains
the single source for the bootstrap count (SPEC B54/C65) and is
re-exported here — never hardcode a second copy.
"""

#: Official-run coverage gate (SPEC B56 / DEN C75: Coverage >= 0.95).
COVERAGE_OFFICIAL_MIN = 0.95

#: Benchmark health gate (SPEC B56 / DEN C72: Health >= 0.80).
HEALTH_MIN = 0.80

#: Judge reliability threshold (SPEC B52: LOW-CONFIDENCE below 0.90).
JUDGE_STABILITY_MIN = 0.90

#: Calibration capability weight (SPEC B55: calibration dim weight 0.05).
CALIBRATION_BAND_WIDTH = 0.05

#: Bootstrap low-sample family threshold (DEN C66: <10 families).
LOW_SAMPLE_FAMILY_THRESHOLD = 10

#: Saturation knee tau (SPEC B49: penalty above 0.95).
SATURATION_TAU = 0.95

#: Harmonic-mean level count for novelty robustness (SPEC B13/B14:
#: harmonic mean over the 3 C/P/N levels).
HARMONIC_K = 3.0

try:
    from scoring import BOOTSTRAP_MAX, BOOTSTRAP_RESAMPLES
except ImportError:  # package-style import (repo root on sys.path)
    try:
        from shared.scoring import BOOTSTRAP_MAX, BOOTSTRAP_RESAMPLES
    except ImportError:  # standalone tooling without the package path
        BOOTSTRAP_RESAMPLES = 10_000
        BOOTSTRAP_MAX = 100_000

#: Hidden-prompt canary (SPEC 38). Digit-free by construction so the
#: integer-answer oracle regex can never match it. Single source: hidden
#: suite prompts AND contamination.canary_check both use this.
CANARY_HIDDEN = ("EMO-X-HIDDEN-CANARY-training-on-this-prompt-is-prohibited-"
                 "benchmark-integrity-tag")
