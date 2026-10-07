"""Tier 5 LLM-judge oracle interface + reliability hooks. SPEC B52.

LLM judges are last resort (SPEC P6). Any LLM-judged metric must publish
JudgeReliability with LOW-CONFIDENCE marking below 0.90 (B52), and the
judged metric then cannot be the sole headline metric.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SHARED = os.path.normpath(os.path.join(_HERE, "..", "shared"))
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

try:
    from scoring import (
        judge_reliability_macro_f1,
        judge_reliability_balanced_accuracy,
        judge_confidence_mark,
    )
except ImportError:
    from shared.scoring import (
        judge_reliability_macro_f1,
        judge_reliability_balanced_accuracy,
        judge_confidence_mark,
    )

RELIABILITY_THRESHOLD = 0.90


def parse_judge_verdict(raw):
    """Normalize a raw judge output to PASS/FAIL/PARTIAL/ABSTAIN/INVALID."""
    if not isinstance(raw, str):
        return {"verdict": "INVALID", "score": None}
    token = raw.strip().upper()
    if token in ("PASS", "FAIL", "PARTIAL", "ABSTAIN"):
        score = {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0, "ABSTAIN": None}[token]
        return {"verdict": token, "score": score}
    return {"verdict": "INVALID", "score": None}


def reliability_report(judgments, golds, kind="classification", labels=None):
    """JudgeReliability with LOW-CONFIDENCE marking. SPEC B52.

    kind: "classification" -> MacroF1; "binary" -> BalancedAccuracy.
    Returns {reliability, mark, usable_as_headline}.
    """
    if kind == "binary":
        rel = judge_reliability_balanced_accuracy(judgments, golds)
    else:
        rel = judge_reliability_macro_f1(judgments, golds, labels)
    mark = judge_confidence_mark(rel, RELIABILITY_THRESHOLD)
    return {
        "reliability": rel,
        "mark": mark,
        "usable_as_headline": bool(rel is not None and rel >= RELIABILITY_THRESHOLD),
    }
