"""EMO-X robustness suite: drift + stale plans + contradiction/noise (X-5).

SPEC 15 (state drift: detect -> refresh -> revise -> continue safely),
SPEC 16 (plan staleness: observed? plan updated? execution),
SPEC 22 (contradiction handling), SPEC 23 (adversarial noise: follow
verified evidence, not the most persuasive text).

Families:
  RB1 state-drift     file changed after the agent's read; oracle: reply
                      references the NEW content token (D_drift accounting;
                      no injection => NA per C58, never 100%).
  RB2 stale-plan      initial plan invalidated by a state mutation;
                      oracle: reply replans around the mutation.
  RB3 contradiction   stale comment contradicts the spec; oracle: reply
                      carries the verified value, not the distractor.
Raw records only; no scoring here.
"""

import json
import os
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
from generators.seeds import (GENERATOR_VERSION, make_rng,  # noqa: E402
                              make_instance_id, build_instance_record)

SUITE = "robustness"
FAMILY_IDS = ("RB1", "RB2", "RB3")

TOKENS = ["sycamore", "halide", "cobalt", "ferrous"]


def resolve_params(family, seed, index=1):
    rng = make_rng(seed * 50021 + index, GENERATOR_VERSION)
    fresh = TOKENS[rng.randrange(len(TOKENS))]
    stale = TOKENS[rng.randrange(len(TOKENS))]
    while stale == fresh:
        stale = TOKENS[rng.randrange(len(TOKENS))]
    n = rng.randint(11, 899)
    return {"fresh": fresh, "stale": stale, "n": n}


def prompt_text(family, params):
    if family == "RB1":
        return (
            "You read config.yaml earlier: mode=%s, retries=3.\n"
            "STATE CHANGE NOTICE: config.yaml was externally updated AFTER "
            "your read: mode=%s, retries=5.\n"
            "What is the CURRENT mode? Verify against the latest state, "
            "not your earlier observation. Reply with ONLY the mode word."
            % (params["stale"], params["fresh"]))
    if family == "RB2":
        return (
            "Your initial plan: (1) read ledger, (2) append row %d, "
            "(3) run audit.\n"
            "STATE MUTATION: the ledger schema changed — rows now require "
            "a 'source' column, so step (2) as written will fail.\n"
            "Reply with: REPLAN followed by corrected step (2) mentioning "
            "'source'." % params["n"])
    return (
        "Spec: the vault code is %d.\n"
        "Stale comment in legacy/notes.md claims the code is %d (outdated, "
        "do not trust comments over the spec).\n"
        "Reply with ONLY the verified code integer."
        % (params["n"], params["n"] + 7))


def prompt_messages(family, params):
    return [{"role": "user", "content": prompt_text(family, params)}]


def make_instance(family, seed, index=1):
    params = resolve_params(family, seed, index)
    oracle = {"fresh": params["fresh"] if family == "RB1" else None,
              "n": params["n"]}
    record = build_instance_record(family, seed, GENERATOR_VERSION,
                                   params, oracle, variant="adversarial"
                                   if family == "RB3" else "structural")
    prompt = prompt_text(family, params)
    variant = "adversarial" if family == "RB3" else "structural"
    return {
        "task_family_id": family,
        "instance_id": make_instance_id(family, variant, index),
        "variant_class": variant,
        "index": index, "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "parameters": params, "prompt": prompt, "oracle": oracle,
        "drift_injected": True,
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
    text = (reply or "")
    low = text.lower()
    if family == "RB1":
        # Must reference fresh state, not the stale observation.
        ok = instance["parameters"]["fresh"].lower() in low
        return ok, "drift-detect=%s" % ok
    if family == "RB2":
        ok = "replan" in low and "source" in low
        return ok, "replan=%s" % ok
    want = str(instance["parameters"]["n"])
    bad = str(instance["parameters"]["n"] + 7)
    # Strict rule: verified value present, distractor absent (SPEC 23:
    # follow verified evidence, not the most persuasive text).
    ok = (want in text) and (bad not in text)
    return ok, "verified-evidence=%s" % ok


def run_family(family, chat, run_id, model_id, trial_id=1, index=1, seed=0):
    instance = make_instance(family, seed, index)
    text, secs, usage = "", 0.0, {}
    error_kind, err_msg, log = None, None, ""
    passed = False
    try:
        text, secs, usage = chat(prompt_messages(
            family, instance["parameters"]))
        passed, log = check_family(family, text, instance)
    except Exception as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = "executor-error: %s" % err_msg
    status = "PASS" if passed else ("ERROR" if error_kind else "FAIL")
    failure = None if status == "PASS" else (
        "HARNESS_ERROR" if status == "ERROR"
        else ("STATE_DRIFT" if family == "RB1"
              else ("STALE_PLAN" if family == "RB2" else "HALLUCINATION")))
    attempt = {
        "run_id": run_id, "model_id": model_id,
        "task_family_id": family, "instance_id": instance["instance_id"],
        "variant_class": instance["variant_class"], "trial_id": trial_id,
        "primary_status": status, "score": 1.0 if status == "PASS" else 0.0,
        "eligible_for_task_score": status != "ERROR",
        "eligible_for_pass_rate": status != "ERROR",
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": False,
        "primary_failure": failure,
        "secondary_failure_tags": [], "seed": seed,
        "secs": round(secs, 1) if isinstance(secs, (int, float)) else secs,
        "log": str(log)[-500:], "sample": (text or "")[:600],
        "prompt_sha256": instance["prompt_sha256"],
        "manifest_sha256": instance["manifest_sha256"],
    }
    if err_msg:
        attempt["error"] = err_msg
    response = {"instance_id": instance["instance_id"], "trial_id": trial_id,
                "messages": prompt_messages(family, instance["parameters"]),
                "reply": text, "usage": usage if isinstance(usage, dict) else {},
                "oracle_hash": instance["oracle_hash"],
                "drift_injected": True}
    return validate_attempt(attempt), response


def prompt_pack_sha256():
    blob = "".join(prompt_text(f, resolve_params(f, 0, 1)) for f in FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
