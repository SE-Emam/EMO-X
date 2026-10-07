"""EMO-X semantic invariants: JSON Schema + Semantic Validator = contract.

schemas.validate_attempt enforces STRUCTURE (fields, types, ranges).
This module enforces SEMANTICS (SPEC B4/B5, DEN C4/C23-C24):

  - PASS means strict pass (S_t == 1, SPEC B4/B5) -> score must be 1.
  - FAIL/TIMEOUT/INVALID/ERROR/VOID are total non-pass -> score must be 0.
  - PARTIAL is a genuine middle -> 0 < score < 1.
  - Non-pass scored attempts must name a primary_failure (SPEC 34:
    infrastructure defects must be classified, never silent).
  - PASS must not carry a failure label.
  - Attempt identity (family, instance, trial) must be unique (DEN C4).
  - trial_id values must be positive ints; per-instance trial sets must
    match the declared trial count when one is given.
  - variant_class must be a non-empty string, and — when a manifest is
    supplied — a member of that family's declared variant classes.

Conventions (binding): stdlib only, pure functions, no I/O, English
code. Violations raise ValueError naming the invariant. None (NA) is
never invented: validators reject, they do not repair.
"""

try:
    from schemas import PRIMARY_STATUSES, SCORED_STATUSES, validate_attempt
except ImportError:
    from shared.schemas import PRIMARY_STATUSES, SCORED_STATUSES, validate_attempt

_EPS = 1e-9

_NON_PASS_SCORED = tuple(s for s in SCORED_STATUSES if s != "PASS")


def _identity(attempt):
    return (attempt.get("task_family_id"), attempt.get("instance_id"), attempt.get("trial_id"))


def validate_failure_taxonomy(record):
    """primary_failure must classify every non-pass, absent on PASS."""
    status = record.get("primary_status")
    failure = record.get("primary_failure")
    if status == "PASS":
        if failure is not None:
            raise ValueError(
                "invariant PASS-has-failure: PASS must carry "
                "primary_failure=null, got %r" % (failure,)
            )
        return True
    if status in SCORED_STATUSES or status in ("ERROR",):
        if not isinstance(failure, str) or not failure.strip():
            raise ValueError(
                "invariant FAIL-without-failure: status %r requires a "
                "non-empty primary_failure string" % (status,)
            )
        return True
    return True


def validate_attempt_semantics(record):
    """Structure (schemas) + status/score + failure + identity shape."""
    validate_attempt(record)
    status = record["primary_status"]
    score = record["score"]
    if status == "PASS":
        if abs(score - 1.0) > _EPS:
            raise ValueError("invariant PASS-score: PASS requires score==1, got %r" % (score,))
    elif status == "PARTIAL":
        if not 0.0 < score < 1.0:
            raise ValueError(
                "invariant PARTIAL-score: PARTIAL requires 0<score<1, got %r" % (score,)
            )
    elif status in PRIMARY_STATUSES:
        if abs(score - 0.0) > _EPS:
            raise ValueError(
                "invariant non-pass-score: status %r requires score==0, got %r" % (status, score)
            )
    variant = record.get("variant_class")
    if not isinstance(variant, str) or not variant.strip():
        raise ValueError("invariant variant-class: non-empty string required, got %r" % (variant,))
    trial = record.get("trial_id")
    if isinstance(trial, bool) or not isinstance(trial, int) or trial < 1:
        raise ValueError("invariant trial-id: positive int required, got %r" % (trial,))
    validate_failure_taxonomy(record)
    return True


def validate_trial_integrity(trials, expected=None):
    """Trial ids for one instance: positive ints, unique, 1..T if known."""
    seen = set()
    for trial in trials:
        if isinstance(trial, bool) or not isinstance(trial, int):
            raise ValueError("invariant trial-id: positive int required, got %r" % (trial,))
        if trial < 1:
            raise ValueError("invariant trial-id: positive int required, got %r" % (trial,))
        if trial in seen:
            raise ValueError("invariant duplicate-trial: trial_id %r twice" % (trial,))
        seen.add(trial)
    if expected is not None and set(seen) != set(range(1, expected + 1)):
        raise ValueError(
            "invariant trial-count: expected trials 1..%d, got %s" % (expected, sorted(seen))
        )
    return True


def validate_variant_integrity(attempts, manifest=None):
    """variant_class values must belong to the manifest declaration."""
    if not manifest:
        for attempt in attempts:
            variant = attempt.get("variant_class")
            if not isinstance(variant, str) or not variant.strip():
                raise ValueError("invariant variant-class: non-empty string required")
        return True
    families = manifest.get("task_families", manifest)
    for attempt in attempts:
        family = attempt.get("task_family_id")
        declared = None
        if isinstance(families, dict):
            entry = families.get(family, {})
            declared = entry.get("variant_classes")
        if declared is not None and attempt.get("variant_class") not in declared:
            raise ValueError(
                "invariant unknown-variant: %r not in manifest variants "
                "for family %r" % (attempt.get("variant_class"), family)
            )
    return True


def validate_run_semantics(attempts, manifest=None, expected_trials=None):
    """Full run gate: per-attempt semantics + uniqueness + trials."""
    seen = set()
    per_instance = {}
    for attempt in attempts:
        validate_attempt_semantics(attempt)
        key = _identity(attempt)
        if key in seen:
            raise ValueError("invariant duplicate-attempt: identity %r twice" % (key,))
        seen.add(key)
        per_instance.setdefault(key[1], []).append(key[2])
    for instance_id, trials in per_instance.items():
        try:
            validate_trial_integrity(trials, expected_trials)
        except ValueError as exc:
            raise ValueError("instance %r: %s" % (instance_id, exc))
    validate_variant_integrity(attempts, manifest)
    return True
