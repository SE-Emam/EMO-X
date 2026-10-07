"""EMO-X dynamic-code suite: parametric instances + mutations (X-5, WP4 ext).

SPEC sections 8-9 (EMO-Core-Dynamic): deterministic seed -> generator ->
instance -> oracle -> execution. Canonical instances go through the
generators factory (seeds.make_rng / make_instance_id /
build_instance_record); variant levels + difficulty bumps are consumed
from generators.mutations (VARIANT_LEVELS, VARIANT_DIFFICULTY_BUMP) —
reimplemented nowhere.

Families:
  DC1 modular-sum      parametric arithmetic, oracle (a+b)%m.
  DC2 string-repeat    parametric string transform, oracle word*k.
Variants per instance: canonical + paraphrase + structural + novel.
Raw records only; no scoring here (X-3 owns scoring).
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
GEN = os.path.join(ROOT, "generators")
for _p in (ROOT, SHARED, GEN):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.schemas import validate_attempt  # noqa: E402
from shared.backends import reasoning_mode_for  # noqa: E402 (Y-5: mode tag)
from shared.manifests import sha256_bytes, sha256_manifest  # noqa: E402
from generators.seeds import (
    GENERATOR_VERSION,
    make_rng,  # noqa: E402
    make_instance_id,
    parse_instance_id,
    build_instance_record,
)
from generators.mutations import (
    VARIANT_LEVELS,  # noqa: E402
    VARIANT_DIFFICULTY_BUMP,
)

SUITE = "dynamic-code"
FAMILY_IDS = ("DC1", "DC2")
VARIANTS = ("canonical", "paraphrase", "structural", "novel")

SPEC_DC1 = {
    "a": {"min": 11, "max": 997},
    "b": {"min": 11, "max": 997},
    "m": {"min": 11, "max": 997},
}
SPEC_DC2 = {"word": {"choices": ["ember", "quarry", "tundra", "vector"]}, "k": {"min": 2, "max": 5}}


def resolve_params(family, seed, index=1):
    """Deterministic parametric draw. SPEC 8 (seed recorded)."""
    rng = make_rng(seed * 100003 + index, GENERATOR_VERSION)
    if family == "DC1":
        return {"a": rng.randint(11, 997), "b": rng.randint(11, 997), "m": rng.randint(11, 997)}
    if family == "DC2":
        words = SPEC_DC2["word"]["choices"]
        return {"word": words[rng.randrange(len(words))], "k": rng.randint(2, 5)}
    raise KeyError("unknown dynamic-code family: %r" % (family,))


def oracle_value(family, params):
    """Deterministic oracle recomputed from parameters (SPEC 6: never in prompt)."""
    if family == "DC1":
        return str((params["a"] + params["b"]) % params["m"])
    if family == "DC2":
        return params["word"] * params["k"]
    raise KeyError(family)


def prompt_text(family, params, variant="canonical"):
    """Prompt builder; structural/novel resample via derived params."""
    if family == "DC1":
        body = "Compute (%d + %d) mod %d. Reply with ONLY the final integer, no explanation." % (
            params["a"],
            params["b"],
            params["m"],
        )
    else:
        body = (
            "Repeat the word %r exactly %d times with no spaces. "
            "Reply with ONLY the result, no explanation." % (params["word"], params["k"])
        )
    if variant == "paraphrase":
        return "Restated: %s Answer with the final value only." % body
    if variant == "structural":
        return (
            "Structural variant — same rule, new numbers. %s Return only the final answer." % body
        )
    if variant == "novel":
        return (
            "Novel instance (unseen numbers). %s "
            "Verify your own work; return only the final answer." % body
        )
    return body


def prompt_messages(family, params, variant="canonical"):
    return [{"role": "user", "content": prompt_text(family, params, variant)}]


def variant_level(variant):
    """SPEC 9 level via generators.mutations (binding, not reinvented)."""
    return VARIANT_LEVELS[variant]


def difficulty_bump(variant):
    """SPEC 10 bump via generators.mutations (binding, not reinvented)."""
    return VARIANT_DIFFICULTY_BUMP[variant]


def make_instance(family, seed, index=1, variant="canonical"):
    """Canonical instance via the generators factory. SPEC 8."""
    params = resolve_params(family, seed, index)
    if variant in ("structural", "novel"):
        # Resampled numbers, still reproducible (SPEC 9 S/N levels).
        rng = make_rng(seed * 100003 + index + 7919, GENERATOR_VERSION)
        if family == "DC1":
            params = {
                "a": rng.randint(11, 997),
                "b": rng.randint(11, 997),
                "m": rng.randint(11, 997),
            }
        else:
            words = SPEC_DC2["word"]["choices"]
            params = {"word": words[rng.randrange(len(words))], "k": rng.randint(2, 5)}
    oracle = {"value": oracle_value(family, params)}
    record = build_instance_record(family, seed, GENERATOR_VERSION, params, oracle, variant=variant)
    prompt = prompt_text(family, params, variant)
    return {
        "task_family_id": family,
        "instance_id": make_instance_id(family, variant, index),
        "variant_class": variant,
        "generalization_level": variant_level(variant),
        "difficulty_bump": difficulty_bump(variant),
        "index": index,
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "parameters": params,
        "prompt": prompt,
        "oracle": oracle,
        "instance_hash": record["instance_hash"],
        "oracle_hash": record["oracle_hash"],
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "manifest_sha256": sha256_manifest(load_manifest(family)),
    }


def load_manifest(family):
    import json

    path = os.path.join(HERE, "manifests", "%s.json" % family)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_family(family, reply, instance):
    """Exact-match oracle against the recomputed value. Returns (pass, log)."""
    expected = instance["oracle"]["value"]
    got = (reply or "").strip().split()[0] if (reply or "").strip() else ""
    if family == "DC1":
        m = re.findall(r"-?\d+", reply or "")
        got = m[-1] if m else ""
    ok = bool(got == expected)
    return ok, "expected=%r got=%r" % (expected, got[:80])


class _MissingTool(RuntimeError):
    pass


def run_family(family, chat, run_id, model_id, trial_id=1, index=1, seed=0, variant="canonical"):
    """Run one instance; returns schema-valid (attempt, response)."""
    instance = make_instance(family, seed, index, variant)
    text, secs, usage = "", 0.0, {}
    error_kind, err_msg, log = None, None, ""
    passed = False
    try:
        text, secs, usage = chat(prompt_messages(family, instance["parameters"], variant))
        passed, log = check_family(family, text, instance)
    except Exception as e:  # harness-side failure -> ERROR, never FAIL
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = "executor-error: %s" % err_msg
    status = "PASS" if passed else ("ERROR" if error_kind else "FAIL")
    attempt = {
        "run_id": run_id,
        "model_id": model_id,
        "task_family_id": family,
        "instance_id": instance["instance_id"],
        "variant_class": variant,
        "trial_id": trial_id,
        "primary_status": status,
        "score": 1.0 if status == "PASS" else 0.0,
        "eligible_for_task_score": status != "ERROR",
        "eligible_for_pass_rate": status != "ERROR",
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": False,
        "primary_failure": None
        if status == "PASS"
        else ("HARNESS_ERROR" if status == "ERROR" else "WRONG_RESULT"),
        "secondary_failure_tags": [],
        "seed": seed,
        "reasoning_mode": reasoning_mode_for(),
        "secs": round(secs, 1) if isinstance(secs, (int, float)) else secs,
        "log": str(log)[-500:],
        "sample": (text or "")[:600],
        "prompt_sha256": instance["prompt_sha256"],
        "manifest_sha256": instance["manifest_sha256"],
    }
    if err_msg:
        attempt["error"] = err_msg
    response = {
        "instance_id": instance["instance_id"],
        "trial_id": trial_id,
        "messages": prompt_messages(family, instance["parameters"], variant),
        "reply": text,
        "usage": usage if isinstance(usage, dict) else {},
        "oracle_hash": instance["oracle_hash"],
        "generalization_level": instance["generalization_level"],
    }
    return validate_attempt(attempt), response


def prompt_pack_sha256():
    """SHA256 over canonical prompts (B58 prompt hash input)."""
    blob = "".join(prompt_text(f, resolve_params(f, 0, 1), "canonical") for f in FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    """SHA256 of this executor file's bytes (B58 harness hash input)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
