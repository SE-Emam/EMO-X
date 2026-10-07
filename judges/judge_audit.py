"""Judge audit: test the judge itself (stdlib only).

An LLM judge is Tier 5 (last resort, SPEC P6) and its verdicts need
auditing for instability and bias — especially across languages, where
recent work finds degraded judge reliability. This module perturbs judge
inputs and measures flip rates: a reliable judge is invariant to
order, verbosity padding, truncation of boilerplate, and conflicting
restatements; a biased judge flips.

Interface: judge_fn(case) -> verdict string (PASS/FAIL/PARTIAL/ABSTAIN/
anything; normalized for comparison). A case is a mapping with at
least {"id", "prompt"} and optionally {"candidates": [A, B],
"alt_language": "...", "gold": "..."}.

Usage:
  audit = audit_judge(cases, judge_fn)
  audit["stability"]  # 1 - mean flip rate over perturbations
  audit["flips"]      # {perturbation: flip_rate}
"""

import re

#: Perturbations every audited judge must survive.
PERTURBATIONS = (
    "order_swap",
    "verbosity_pad",
    "truncate_tail",
    "conflicting_restatement",
    "language_dual",
)

_VERBOSITY_PAD = (
    "\n\nNote: the response above is detailed and thorough, well formatted "
    "with clear structure and careful reasoning throughout its length. " * 3
)

_CONFLICT_NOTE = (
    "\n\nA second reviewer disagrees and claims the opposite conclusion "
    "holds. Decide on the evidence in the original response only."
)


def _norm(verdict):
    return (verdict or "").strip().upper()


def perturb(case, kind):
    """Return a perturbed copy of a judge case. Pure (no mutation)."""
    out = dict(case)
    prompt = case.get("prompt", "")
    cands = list(case.get("candidates", []) or [])
    if kind == "order_swap":
        if len(cands) >= 2:
            out["candidates"] = [cands[1], cands[0]] + cands[2:]
        else:
            out["prompt"] = "Option B first, then option A. " + prompt
    elif kind == "verbosity_pad":
        out["prompt"] = prompt + _VERBOSITY_PAD
    elif kind == "truncate_tail":
        out["prompt"] = prompt[: max(len(prompt) // 2, 1)]
    elif kind == "conflicting_restatement":
        out["prompt"] = prompt + _CONFLICT_NOTE
    elif kind == "language_dual":
        alt = case.get("alt_language")
        out["prompt"] = (prompt + "\n\n" + alt) if alt else prompt
    else:
        raise ValueError("unknown audit perturbation: %r" % (kind,))
    return out


def audit_judge(cases, judge_fn, kinds=None):
    """Audit judge stability. Returns {flips, stability, n}.

    flips[kind] = fraction of cases whose normalized verdict changed
    under that perturbation. stability = 1 - mean(flips). A case whose
    perturbation is a no-op (e.g. language_dual without alt_language)
    is excluded from that perturbation's denominator (NA, not zero).
    """
    kinds = list(kinds or PERTURBATIONS)
    flips = {}
    for kind in kinds:
        changed, total = 0, 0
        for case in cases:
            pert = perturb(case, kind)
            if pert.get("prompt") == case.get("prompt") and pert.get("candidates") == case.get(
                "candidates"
            ):
                continue  # no-op perturbation: excluded (NA)
            total += 1
            try:
                base = _norm(judge_fn(case))
            except Exception:
                base = "ERROR"
            try:
                new = _norm(judge_fn(pert))
            except Exception:
                new = "ERROR"
            if new != base:
                changed += 1
        flips[kind] = (changed / total) if total else None
    rated = [v for v in flips.values() if v is not None]
    return {
        "flips": flips,
        "stability": (1.0 - sum(rated) / len(rated)) if rated else None,
        "n": len(list(cases)),
    }


def audit_mark(stability, threshold=0.90):
    """Stability mark mirroring the B52 reliability gate language."""
    if stability is None:
        return "UNEVALUATED"
    return "STABLE" if stability >= threshold else "UNSTABLE"
