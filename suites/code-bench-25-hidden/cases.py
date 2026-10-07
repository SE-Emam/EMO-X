"""EMO-X code-bench-25-hidden suite: runtime-only hidden instances (Y-4).

SPEC section 38 (contamination defense): hidden families generate
instances at runtime from generator CONFIG + seeds. No instance, prompt,
or seed is ever stored in the repo. The prompt-pack hash covers the
generator CONFIG only, never instances.

Families:
  HH1 modular-equation hard  a*v == b (mod m), large modulus, unique solution.
  HH2 code-task variant      pow(base, exponent, modulus), exact integer.
  HH3 reasoning              positional weighted checksum mod modulus.
  HH4 reasoning              lcm(a, b) for large coprime-shifted pairs.
  HH5 code-task variant      digit-sum of N in base B (B in 2..16).
  HH6 reasoning              sum of multiples of d in [1, N], large N.

All oracles are deterministic (SPEC P6 Tier 1). Every instance carries
variant_class "hidden" and an instance_id of the form
"{family}-hidden-{index:05d}" via generators.seeds.make_instance_id.

Canary (SPEC 38): every hidden prompt carries a digit-free integrity
tag (CANARY). It contains no digits, so the integer oracle regex is
unaffected; its presence in training data proves prompt leakage.

Stdlib only. English code.
"""

import json
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
from shared.manifests import sha256_bytes, sha256_manifest  # noqa: E402
from generators.seeds import (
    GENERATOR_VERSION,
    make_rng,  # noqa: E402
    make_instance_id,
    parse_instance_id,
    build_instance_record,
)

SUITE = "code-bench-25-hidden"
FAMILY_IDS = ("HH1", "HH2", "HH3", "HH4", "HH5", "HH6")
HIDDEN_VARIANT = "hidden"

#: Digit-free canary: no [0-9], so the integer-answer regex in
#: check_family can never match it. Presence of this tag in any
#: training corpus proves hidden-prompt leakage (SPEC 38). Single
#: source in shared/constants (CANARY_HIDDEN) — contamination.py
#: canary_check detects the same tag.
try:
    from constants import CANARY_HIDDEN as CANARY
except ImportError:
    from shared.constants import CANARY_HIDDEN as CANARY

HH1_VAR_NAMES = ("x", "n", "k", "t")


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def resolve_params(family, seed, index=1):
    """Deterministic parametric draw from generator CONFIG. SPEC 8."""
    rng = make_rng(seed * 100003 + index, GENERATOR_VERSION)
    if family == "HH1":
        modulus = rng.randint(211, 997)
        coefficient = 1
        for _ in range(500):
            candidate = rng.randint(2, modulus + 20)
            if _gcd(candidate, modulus) == 1:
                coefficient = candidate
                break
        target = rng.randint(1, 199)
        var = HH1_VAR_NAMES[rng.randrange(len(HH1_VAR_NAMES))]
        return {"coefficient": coefficient, "target": target, "modulus": modulus, "variable": var}
    if family == "HH2":
        return {
            "base": rng.randint(2, 50),
            "exponent": rng.randint(10, 60),
            "modulus": rng.randint(101, 997),
        }
    if family == "HH3":
        return {"items": [rng.randint(1, 99) for _ in range(5)], "modulus": rng.randint(101, 997)}
    if family == "HH4":
        base = rng.randint(101, 499)
        return {"a": base * rng.randint(2, 9), "b": base * rng.randint(2, 9)}
    if family == "HH5":
        return {"n": rng.randint(10**6, 10**9), "base": rng.randint(2, 16)}
    if family == "HH6":
        return {"d": rng.randint(3, 49), "n": rng.randint(10**5, 10**6)}
    raise KeyError("unknown hidden family: %r" % (family,))


def _digit_sum(n, base):
    total = 0
    while n:
        total += n % base
        n //= base
    return total


def oracle_value(family, params):
    """Deterministic oracle recomputed from parameters (never in prompt)."""
    if family == "HH1":
        inv = pow(params["coefficient"], -1, params["modulus"])
        return str((inv * params["target"]) % params["modulus"])
    if family == "HH2":
        return str(pow(params["base"], params["exponent"], params["modulus"]))
    if family == "HH3":
        total = sum((i + 1) * v for i, v in enumerate(params["items"]))
        return str(total % params["modulus"])
    if family == "HH4":
        a, b = params["a"], params["b"]
        return str(a * b // _gcd(a, b))
    if family == "HH5":
        return str(_digit_sum(params["n"], params["base"]))
    if family == "HH6":
        d, n = params["d"], params["n"]
        count = n // d
        return str(d * count * (count + 1) // 2)
    raise KeyError(family)


def _canary_line():
    """Integrity tag appended to every hidden prompt (SPEC 38)."""
    return "Benchmark integrity tag (ignore, reply integer only): " + CANARY


def prompt_text(family, params):
    """Prompt builder. Contains the question, never the oracle answer."""
    if family == "HH1":
        return (
            "Solve for %(v)s: %(a)d * %(v)s == %(b)d (mod %(m)d). "
            "There is a unique solution with 0 <= %(v)s < %(m)d. "
            "Reply with ONLY the final integer, no explanation. "
            "%(canary)s"
            % {
                "v": params["variable"],
                "a": params["coefficient"],
                "b": params["target"],
                "m": params["modulus"],
                "canary": _canary_line(),
            }
        )
    if family == "HH2":
        return (
            "Compute (%(b)d ** %(e)d) mod %(m)d. "
            "Reply with ONLY the final integer, no explanation. "
            "%(canary)s"
            % {
                "b": params["base"],
                "e": params["exponent"],
                "m": params["modulus"],
                "canary": _canary_line(),
            }
        )
    if family == "HH3":
        items = ", ".join(str(v) for v in params["items"])
        return (
            "Given the list [%s], compute the weighted checksum "
            "sum((position) * value) for positions 1..5, "
            "then take it mod %d. "
            "Reply with ONLY the final integer, no explanation. "
            "%s" % (items, params["modulus"], _canary_line())
        )
    if family == "HH4":
        return (
            "Compute lcm(%(a)d, %(b)d) (least common multiple). "
            "Reply with ONLY the final integer, no explanation. "
            "%(canary)s" % {"a": params["a"], "b": params["b"], "canary": _canary_line()}
        )
    if family == "HH5":
        return (
            "Express %(n)d in base %(b)d, then compute the sum of "
            "its base-%(b)d digits. "
            "Reply with ONLY the final integer, no explanation. "
            "%(canary)s" % {"n": params["n"], "b": params["base"], "canary": _canary_line()}
        )
    if family == "HH6":
        return (
            "Compute the sum of all multiples of %(d)d in "
            "[1, %(n)d]. "
            "Reply with ONLY the final integer, no explanation. "
            "%(canary)s" % {"d": params["d"], "n": params["n"], "canary": _canary_line()}
        )
    raise KeyError(family)


def prompt_messages(family, params):
    return [{"role": "user", "content": prompt_text(family, params)}]


def make_instance(family, seed, index=1):
    """Build one hidden instance at runtime. Never touches disk."""
    if family not in FAMILY_IDS:
        raise KeyError("unknown hidden family: %r" % (family,))
    params = resolve_params(family, seed, index)
    oracle = {"value": oracle_value(family, params)}
    record = build_instance_record(
        family, seed, GENERATOR_VERSION, params, oracle, variant=HIDDEN_VARIANT
    )
    prompt = prompt_text(family, params)
    return {
        "task_family_id": family,
        "instance_id": make_instance_id(family, HIDDEN_VARIANT, index),
        "variant_class": HIDDEN_VARIANT,
        "generalization_level": "hidden",
        "difficulty_bump": 0,
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
    path = os.path.join(HERE, "manifests", "%s.json" % family)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_family(family, reply, instance):
    """Exact-match oracle against the recomputed value. Returns (ok, log)."""
    expected = instance["oracle"]["value"]
    found = re.findall(r"-?\d+", reply or "")
    got = found[-1] if found else ""
    ok = bool(got == expected)
    return ok, "expected=%r got=%r" % (expected, got[:80])


def run_family(family, chat, run_id, model_id, trial_id=1, index=1, seed=0):
    """Run one hidden instance; returns schema-valid (attempt, response)."""
    instance = make_instance(family, seed, index)
    text, secs, usage = "", 0.0, {}
    error_kind, err_msg, log = None, None, ""
    passed = False
    try:
        text, secs, usage = chat(prompt_messages(family, instance["parameters"]))
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
        "variant_class": HIDDEN_VARIANT,
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
        "messages": prompt_messages(family, instance["parameters"]),
        "reply": text,
        "usage": usage if isinstance(usage, dict) else {},
        "oracle_hash": instance["oracle_hash"],
        "generalization_level": instance["generalization_level"],
    }
    return validate_attempt(attempt), response


def prompt_pack_sha256():
    """SHA256 over generator CONFIG only (never instances). SPEC 38.

    Hashes the canonical {generator, oracle} descriptors from the three
    hidden manifests, so rotating seeds or generating instances does not
    change the hash, while any generator-config change does.
    """
    parts = []
    for family in FAMILY_IDS:
        manifest = load_manifest(family)
        parts.append(
            json.dumps(
                {
                    "generator": manifest["generator"],
                    "id": manifest["id"],
                    "oracle": manifest["oracle"],
                },
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    blob = "|".join(parts)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    """SHA256 of this cases file's bytes (B58 harness hash input)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
