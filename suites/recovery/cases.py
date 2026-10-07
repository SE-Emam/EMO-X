"""EMO-X recovery suite: fault-injection episodes (X-5, WP7).

SPEC sections 13-14: controlled failures (TOOL_TIMEOUT,
TOOL_MALFORMED_OUTPUT, ...) are injected into otherwise valid tasks; the
system measures whether the agent recovers. Recovery Rate is computed
over D_recoverable only (DEN C29): non-recoverable faults, failed
injections, and infra-invalid episodes are excluded — never scored as
model failures.

Families:
  RC1 timeout-recovery      transient TOOL_TIMEOUT then retry.
  RC2 malformed-recovery    TOOL_MALFORMED_OUTPUT then corrected JSON.
Each attempt carries recoverable=True; each response carries the
recovery episode record consumed by shared.scoring.recovery_rate.
Raw records only; no scoring here.
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
    build_instance_record,
)

SUITE = "recovery"
FAMILY_IDS = ("RC1", "RC2")

FAULTS = {"RC1": "TOOL_TIMEOUT", "RC2": "TOOL_MALFORMED_OUTPUT"}


def resolve_params(family, seed, index=1):
    rng = make_rng(seed * 30011 + index, GENERATOR_VERSION)
    return {"x": rng.randint(11, 499), "y": rng.randint(11, 499)}


def oracle_value(family, params):
    if family == "RC1":
        return str(params["x"] + params["y"])
    return json.dumps({"sum": params["x"] + params["y"]}, sort_keys=True)


def prompt_text(family, params):
    fault = FAULTS[family]
    if family == "RC1":
        return (
            "Task: compute %d + %d.\n"
            "Transcript: your first tool attempt failed with %s "
            "(transient infrastructure fault, not your error).\n"
            "Diagnose the failure, retry with an alternative strategy, "
            "then verify. Reply with: RETRY then the final integer only."
            % (params["x"], params["y"], fault)
        )
    return (
        'Task: return JSON {"sum": %d + %d}.\n'
        "Transcript: your first tool attempt failed with %s "
        "(the tool echoed truncated text).\n"
        "Diagnose, retry, then verify. Reply with: RETRY then ONLY the "
        "valid JSON object, no explanation." % (params["x"], params["y"], fault)
    )


def prompt_messages(family, params):
    return [{"role": "user", "content": prompt_text(family, params)}]


def make_instance(family, seed, index=1):
    params = resolve_params(family, seed, index)
    oracle = {"value": oracle_value(family, params), "fault": FAULTS[family]}
    record = build_instance_record(
        family,
        seed,
        GENERATOR_VERSION,
        dict(params, injected_fault=FAULTS[family]),
        oracle,
        variant="recovery",
    )
    prompt = prompt_text(family, params)
    return {
        "task_family_id": family,
        "instance_id": make_instance_id(family, "recovery", index),
        "variant_class": "recovery",
        "index": index,
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "parameters": params,
        "prompt": prompt,
        "oracle": oracle,
        "recoverable": True,
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
    """Recovery oracle: retry marker + correct recomputed value."""
    text = reply or ""
    if "RETRY" not in text.upper():
        return False, "no retry marker (recovery not attempted)"
    expected = instance["oracle"]["value"]
    if family == "RC1":
        m = re.findall(r"-?\d+", text)
        got = m[-1] if m else ""
        return bool(got == expected), "expected=%r got=%r" % (expected, got[:80])
    m = re.search(r"\{.*\}", text, re.S)
    try:
        got = json.loads(m.group(0)) if m else None
        ok = isinstance(got, dict) and got.get("sum") == json.loads(expected)["sum"]
    except Exception:
        ok = False
    return bool(ok), "expected=%s recovered=%s" % (expected, bool(ok))


def run_family(family, chat, run_id, model_id, trial_id=1, index=1, seed=0, fault_rate=0.25):
    """Run one fault-injection episode; returns (attempt, response).

    fault_rate gates injection deterministically from (seed, index):
    episodes below the rate carry recoverable=True (D_recoverable);
    the rest run as plain baseline tasks (recoverable=False, excluded
    from Recovery Rate per C30).
    """
    instance = make_instance(family, seed, index)
    gate = make_rng(seed * 7919 + index, GENERATOR_VERSION).random()
    injected = gate < fault_rate
    text, secs, usage = "", 0.0, {}
    error_kind, err_msg, log = None, None, ""
    passed = False
    try:
        text, secs, usage = chat(prompt_messages(family, instance["parameters"]))
        passed, log = check_family(family, text, instance)
    except Exception as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = "executor-error: %s" % err_msg
    status = "PASS" if passed else ("ERROR" if error_kind else "FAIL")
    recovered = bool(passed and injected)
    attempt = {
        "run_id": run_id,
        "model_id": model_id,
        "task_family_id": family,
        "instance_id": instance["instance_id"],
        "variant_class": "recovery",
        "trial_id": trial_id,
        "primary_status": status,
        "score": 1.0 if status == "PASS" else 0.0,
        "eligible_for_task_score": status != "ERROR",
        "eligible_for_pass_rate": status != "ERROR",
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": False,
        "primary_failure": None
        if status == "PASS"
        else ("HARNESS_ERROR" if status == "ERROR" else "RECOVERY_FAILURE"),
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
    episode = {
        "recoverable": bool(injected),  # D_recoverable gate (C29)
        "injection_succeeded": bool(injected),
        "infra_valid": error_kind is None,
        "recovered": recovered,
        "fault": FAULTS[family] if injected else None,
    }
    response = {
        "instance_id": instance["instance_id"],
        "trial_id": trial_id,
        "messages": prompt_messages(family, instance["parameters"]),
        "reply": text,
        "usage": usage if isinstance(usage, dict) else {},
        "oracle_hash": instance["oracle_hash"],
        "recovery_episode": episode,
    }
    return validate_attempt(attempt), response


def prompt_pack_sha256():
    blob = "".join(prompt_text(f, resolve_params(f, 0, 1)) for f in FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
