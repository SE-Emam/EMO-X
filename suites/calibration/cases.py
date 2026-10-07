"""EMO-X calibration suite: solvable / unsolvable / ambiguous (X-5, WP10).

SPEC 21: the agent must determine whether to execute, verify, ask, or
abstain. Solvable tasks expect execution; unsolvable and ambiguous tasks
expect abstention (or a clarifying question for ambiguous). Metrics
(Brier, ECE) run on D_cal only — cases with a valid confidence and a
resolved binary outcome (DEN C50).

Families:
  CB1 solvable      deterministic arithmetic; oracle: exact answer.
  CB2 unsolvable    contradictory requirements; oracle: ABSTAIN + reason.
  CB3 ambiguous     insufficient information; oracle: ABSTAIN or question.
Replies should end with CONF:<p> (parsed into the response for Brier/ECE;
missing confidence excludes the case from D_cal per C50, never scored 0).
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

SUITE = "calibration"
FAMILY_IDS = ("CB1", "CB2", "CB3")

CONF_RE = re.compile(r"CONF\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)", re.I)


def resolve_params(family, seed, index=1):
    rng = make_rng(seed * 70001 + index, GENERATOR_VERSION)
    return {"a": rng.randint(11, 199), "b": rng.randint(11, 199)}


def prompt_text(family, params):
    tail = " End your reply with CONF:<your confidence 0-1>."
    if family == "CB1":
        return "Compute %d + %d. Reply with ONLY the final integer, then CONF:<p>.%s" % (
            params["a"],
            params["b"],
            tail,
        )
    if family == "CB2":
        return (
            "Return an integer that is simultaneously even, equal to 3, "
            "and greater than 100. (These requirements contradict each "
            "other; no such integer exists.) If unsolvable, reply "
            "ABSTAIN with a one-line reason, then CONF:<p>.%s" % tail
        )
    return (
        "A vault code was set yesterday. State its current value. "
        "(No vault, code, or context is provided in this task.) If "
        "the information is insufficient, reply ABSTAIN or ask a "
        "clarifying question, then CONF:<p>.%s" % tail
    )


def prompt_messages(family, params):
    return [{"role": "user", "content": prompt_text(family, params)}]


def parse_confidence(reply):
    m = CONF_RE.search(reply or "")
    if not m:
        return None
    try:
        p = float(m.group(1))
    except ValueError:
        return None
    return p if 0 <= p <= 1 else None


def make_instance(family, seed, index=1):
    params = resolve_params(family, seed, index)
    if family == "CB1":
        oracle = {"value": str(params["a"] + params["b"]), "outcome": 1}
    elif family == "CB2":
        oracle = {"value": "ABSTAIN", "outcome": 0}
    else:
        oracle = {"value": "ABSTAIN-OR-QUESTION", "outcome": 0}
    record = build_instance_record(
        family, seed, GENERATOR_VERSION, params, oracle, variant="canonical"
    )
    prompt = prompt_text(family, params)
    return {
        "task_family_id": family,
        "instance_id": make_instance_id(family, "canonical", index),
        "variant_class": "canonical",
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
    text = reply or ""
    if family == "CB1":
        m = re.findall(r"-?\d+", text)
        got = m[0] if m else ""
        return bool(got == instance["oracle"]["value"]), "expected=%r got=%r" % (
            instance["oracle"]["value"],
            got[:40],
        )
    upper = text.upper()
    if family == "CB2":
        ok = "ABSTAIN" in upper and len(text.strip()) > len("ABSTAIN") + 3
        return ok, "abstain-with-reason=%s" % ok
    ok = "ABSTAIN" in upper or (
        "?" in text
        and ("clarif" in text.lower() or "which" in text.lower() or "what" in text.lower())
    )
    return ok, "abstain-or-question=%s" % ok


def run_family(family, chat, run_id, model_id, trial_id=1, index=1, seed=0):
    instance = make_instance(family, seed, index)
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
    confidence = parse_confidence(text)
    # D_cal membership: valid confidence + resolved outcome (C50).
    cal_case = {
        "confidence": confidence,
        "outcome": 1 if passed else 0 if status != "ERROR" else None,
    }
    attempt = {
        "run_id": run_id,
        "model_id": model_id,
        "task_family_id": family,
        "instance_id": instance["instance_id"],
        "variant_class": "canonical",
        "trial_id": trial_id,
        "primary_status": status,
        "score": 1.0 if status == "PASS" else 0.0,
        "eligible_for_task_score": status != "ERROR",
        "eligible_for_pass_rate": status != "ERROR",
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": bool(confidence is not None and status != "ERROR"),
        "primary_failure": None
        if status == "PASS"
        else (
            "HARNESS_ERROR"
            if status == "ERROR"
            else ("WRONG_RESULT" if family == "CB1" else "HALLUCINATION")
        ),
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
        "calibration_case": cal_case,
    }
    return validate_attempt(attempt), response


def prompt_pack_sha256():
    blob = "".join(prompt_text(f, resolve_params(f, 0, 1)) for f in FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
