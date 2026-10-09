"""EMO-X attempt/run/task-manifest validators (stdlib only).

Contract refs: SPEC sections 32-34, DEN C4, C83, C90-C91.
"""

PRIMARY_STATUSES = ("PASS", "PARTIAL", "FAIL", "TIMEOUT", "INVALID", "ERROR", "VOID")
SCORED_STATUSES = ("PASS", "PARTIAL", "FAIL", "TIMEOUT", "INVALID")

# SPEC section 37 (Y-5): closed reasoning-mode vocabulary.
# Produced by shared/backends.py:reasoning_mode_for, validated here (Y-1).
VALID_REASONING_MODES = ("enabled", "disabled", "provider_default", "native")

ATTEMPT_REQUIRED = (
    "run_id",
    "model_id",
    "task_family_id",
    "instance_id",
    "variant_class",
    "trial_id",
    "primary_status",
    "score",
)

ELIGIBILITY_FLAGS = (
    "eligible_for_task_score",
    "eligible_for_pass_rate",
    "eligible_for_efficiency",
    "eligible_for_calibration",
)

# SPEC section 32 fields for run_manifest.json.
RUN_MANIFEST_REQUIRED = (
    "benchmark_version",
    "suite",
    "prompt_pack",
    "prompt_sha256",
    "harness_sha256",
    "model",
    "backend",
    "seed",
    "trials",
)
RUN_MANIFEST_OPTIONAL = (
    "model_sha256",
    "temperature",
    "top_p",
    "top_k",
    "context",
    "reasoning_mode",
    "hardware",
    "runtime",
    "provider_profile",
    "backend_capabilities",
    "claim_tier",
    "reasoning_conditions",
)

# SPEC section 7 (Task DSL) fields for a task manifest.
TASK_MANIFEST_REQUIRED = (
    "id",
    "version",
    "name",
    "category",
    "capabilities",
    "generator",
    "difficulty",
    "execution",
    "oracle",
    "scoring",
    "variants",
    "timeouts",
    "network",
    "filesystem",
)

# Sprint 2: optional vision task-manifest fields (additive, backward-compat).
# V1-V6 manifests omit these (default image_count=1, single-image).
# V7 declares image_count=2 + modalities ["text","image","image"].
VISION_IMAGE_COUNT_DEFAULT = 1
VISION_MODALITIES_DEFAULT = ("text", "image")


class SchemaError(ValueError):
    """Raised when a record fails schema validation."""


def _err(msg):
    return SchemaError(msg)


def validate_attempt(record):
    """Validate one attempt record. Returns normalized dict. DEN C83.

    Rejects: missing identity fields (DEN C4), bad primary_status
    (SPEC 34), score outside [0,1], bad eligibility flags.
    """
    if not isinstance(record, dict):
        raise _err("attempt must be a dict")
    for field in ATTEMPT_REQUIRED:
        if field not in record:
            raise _err("attempt missing required field: %s" % field)
    status = record["primary_status"]
    if status not in PRIMARY_STATUSES:
        raise _err("bad primary_status: %r" % (status,))
    score = record["score"]
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise _err("score must be a number in [0,1]")
    if not (0 <= score <= 1):
        raise _err("score out of range [0,1]: %r" % (score,))
    trial = record["trial_id"]
    if isinstance(trial, bool) or not isinstance(trial, int) or trial < 1:
        raise _err("trial_id must be a positive int")
    for field in ("run_id", "model_id", "task_family_id", "instance_id", "variant_class"):
        val = record[field]
        if not isinstance(val, str) or not val:
            raise _err("%s must be a non-empty string" % field)
    out = dict(record)
    out["score"] = float(score)
    for flag in ELIGIBILITY_FLAGS:
        if flag in out and not isinstance(out[flag], bool):
            raise _err("%s must be bool" % flag)
    if "primary_failure" in out:
        if out["primary_failure"] is not None and (
            not isinstance(out["primary_failure"], str) or not out["primary_failure"]
        ):
            raise _err("primary_failure must be a string or null")
    if "secondary_failure_tags" in out:
        tags = out["secondary_failure_tags"]
        if not isinstance(tags, list) or not all(isinstance(t, str) and t for t in tags):
            raise _err("secondary_failure_tags must be a list of strings")
    return out


def validate_run_manifest(record):
    """Validate run_manifest.json. Returns normalized dict. SPEC 32."""
    if not isinstance(record, dict):
        raise _err("run manifest must be a dict")
    for field in RUN_MANIFEST_REQUIRED:
        if field not in record:
            raise _err("run manifest missing required field: %s" % field)
    if not isinstance(record["trials"], int) or record["trials"] < 1:
        raise _err("trials must be a positive int")
    if not isinstance(record["seed"], int):
        raise _err("seed must be an int")
    if "reasoning_mode" in record:
        if record["reasoning_mode"] not in VALID_REASONING_MODES:
            raise _err("bad reasoning_mode: %r" % (record["reasoning_mode"],))
    if "backend_capabilities" in record:  # SPEC 36: structural check only
        caps = record["backend_capabilities"]
        if not isinstance(caps, dict):
            raise _err("backend_capabilities must be a mapping")
        for field in ("backend", "provider_profile"):
            if field in caps and not isinstance(caps[field], str):
                raise _err("backend_capabilities.%s must be a string" % field)
    if "model_modalities" in record:  # model-level capabilities
        mods = record["model_modalities"]
        if (
            not isinstance(mods, list)
            or not mods
            or any(not isinstance(m, str) or not m.strip() for m in mods)
        ):
            raise _err("model_modalities must be a non-empty string list")
    if "model_type" in record and record["model_type"] is not None:
        if not isinstance(record["model_type"], str) or not record["model_type"].strip():
            raise _err("model_type must be a non-empty string or null")
    for field in ("temperature", "top_p"):
        if field in record and record[field] is not None:
            val = record[field]
            if not isinstance(val, (int, float)) or not (0 <= val <= 1):
                raise _err("%s must be in [0,1]" % field)
    return dict(record)


def validate_task_manifest(record):
    """Validate a Task DSL manifest. Returns normalized dict. SPEC 7."""
    if not isinstance(record, dict):
        raise _err("task manifest must be a dict")
    for field in TASK_MANIFEST_REQUIRED:
        if field not in record:
            raise _err("task manifest missing required field: %s" % field)
    if not isinstance(record["capabilities"], list) or not record["capabilities"]:
        raise _err("capabilities must be a non-empty list")
    if not isinstance(record["variants"], list) or not record["variants"]:
        raise _err("variants must be a non-empty list")
    for section in (
        "generator",
        "difficulty",
        "execution",
        "oracle",
        "scoring",
        "timeouts",
        "network",
        "filesystem",
    ):
        if not isinstance(record[section], dict):
            raise _err("%s must be a mapping" % section)
    net = record["network"]
    if "allowed" in net and not isinstance(net["allowed"], bool):
        raise _err("network.allowed must be bool")
    fs = record["filesystem"]
    if "sandbox_only" in fs and not isinstance(fs["sandbox_only"], bool):
        raise _err("filesystem.sandbox_only must be bool")
    # Sprint 2 (additive, backward-compat): optional vision fields.
    # V1-V6 omit these (default image_count=1, modalities=["text","image"]).
    # V7 declares image_count=2 + modalities=["text","image","image"].
    if "image_count" in record:
        ic = record["image_count"]
        if isinstance(ic, bool) or not isinstance(ic, int) or ic < 1:
            raise _err("image_count must be a positive int")
    if "modalities" in record:
        mods = record["modalities"]
        if (
            not isinstance(mods, list)
            or not mods
            or any(not isinstance(m, str) or not m.strip() for m in mods)
        ):
            raise _err("modalities must be a non-empty string list")
        if "image_count" in record and len(mods) != record["image_count"] + 1:
            raise _err("modalities length must equal image_count + 1 (text + images)")
    if "fixture_sha" in record and record["fixture_sha"] is not None:
        sha = record["fixture_sha"]
        if not isinstance(sha, str) or not sha.strip():
            raise _err("fixture_sha must be a non-empty string")
    if "fixtures" in record:
        fixs = record["fixtures"]
        if (
            not isinstance(fixs, list)
            or not fixs
            or any(not isinstance(f, str) or not f.strip() for f in fixs)
        ):
            raise _err("fixtures must be a non-empty string list")
    if "fixtures_sha" in record:
        shas = record["fixtures_sha"]
        if (
            not isinstance(shas, list)
            or not shas
            or any(not isinstance(s, str) or not s.strip() for s in shas)
        ):
            raise _err("fixtures_sha must be a non-empty string list")
        if "fixtures" in record and len(shas) != len(record["fixtures"]):
            raise _err("fixtures_sha length must match fixtures length")
    return dict(record)


def vision_image_count(manifest_dict):
    """Return manifest image_count with default 1 (Sprint 2)."""
    try:
        ic = (manifest_dict or {}).get("image_count", VISION_IMAGE_COUNT_DEFAULT)
    except AttributeError:
        return VISION_IMAGE_COUNT_DEFAULT
    if isinstance(ic, bool) or not isinstance(ic, int) or ic < 1:
        raise _err("image_count must be a positive int")
    return ic


def vision_modalities(manifest_dict):
    """Return manifest modalities with default ["text","image"] (Sprint 2)."""
    mods = (manifest_dict or {}).get("modalities")
    if mods is None:
        return ["text", "image"]
    if (
        not isinstance(mods, list)
        or not mods
        or any(not isinstance(m, str) or not m.strip() for m in mods)
    ):
        raise _err("modalities must be a non-empty string list")
    return list(mods)


def attempt_identity(record):
    """Return canonical attempt identity tuple. DEN C4."""
    return (record["run_id"], record["task_family_id"], record["instance_id"], record["trial_id"])


def is_scored_status(status):
    """True if status counts toward model performance. DEN C5/C9."""
    return status in SCORED_STATUSES


def na_or_zero(denominator, numerator):
    """Return NA (None) when D==0 else numerator/denominator. DEN C90-C91."""
    if denominator == 0:
        return None
    return numerator / denominator


class VoidRun(Exception):
    """Raised when a round is void (excluded from scoring). SPEC B2, DEN C6."""


STATUS_CAUSES = {
    "harness-bug": "VOID",
    "backend-unavailable": "VOID",
    "prompt-changed": "VOID",
    "infra-crash": "ERROR",
    "model-malformed-output": "FAIL",
    "model-timeout": "TIMEOUT",
    "missing-tool": "ERROR",
}


def classify_cause(cause):
    """Map a failure cause to its primary status. SPEC B2, DEN C5-C6.

    Returns the status string; raises SchemaError on unknown cause.
    """
    try:
        return STATUS_CAUSES[cause]
    except KeyError:
        raise _err("unknown cause: %r" % (cause,))


VISIBILITY = ("public", "hidden", "rotating")


def normalize_visibility(manifest_dict):
    """Default visibility is public; reject unknown. DEN C5, Y-4 contract."""
    v = (manifest_dict or {}).get("visibility", "public")
    if v not in VISIBILITY:
        raise _err("bad visibility: %r" % (v,))
    return v
