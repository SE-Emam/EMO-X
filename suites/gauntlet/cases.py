"""EMO-X Gauntlet: compound flagship scenario (X-5, WP14). SPEC 28.

One scenario interleaves >=7 dimensions in a single episode:

  1. ambiguous requirement      (state the assumption explicitly)
  2. stale documentation        (ignore the outdated README note)
  3. tool failure               (first attempt TOOL_TIMEOUT -> RETRY)
  4. state change               (config updated mid-task -> use CURRENT)
  5. misleading benign note     (distractor value must not appear)
  6. hidden edge case           (empty input must yield 0, not a crash)
  7. test failure               (fix the off-by-one, show FIXED line)
  8. recovery opportunity       (RETRY/REPLAN markers)
  9. final verification         (VERIFY block with the confirmed total)

Solving a single subtask is not enough by design: the oracle scores
each stage (partial credit), PASS requires all stages. Raw records
only; no scoring here.
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
from generators.seeds import (GENERATOR_VERSION, make_rng,  # noqa: E402
                              make_instance_id, build_instance_record)

SUITE = "gauntlet"
FAMILY_IDS = ("GT1",)

DIMENSIONS = ("ambiguous-requirement", "stale-documentation",
              "tool-failure", "state-change", "misleading-note",
              "hidden-edge-case", "test-failure", "recovery-opportunity",
              "final-verification")


def resolve_params(family, seed, index=1):
    rng = make_rng(seed * 110003 + index, GENERATOR_VERSION)
    return {"base": rng.randint(20, 200), "delta": rng.randint(2, 15)}


def prompt_text(family, params):
    total = params["base"] + params["delta"]
    return (
        "GAUNTLET compound scenario (all stages matter; partial stages "
        "earn partial credit).\n"
        "1. AMBIGUOUS REQUIREMENT: 'total the adjusted ledger'. The "
        "adjustment rule is not fully specified — state your assumption "
        "explicitly with ASSUME: <rule>.\n"
        "2. STALE DOCUMENTATION: README claims the base is %d (outdated). "
        "The verified base is %d — follow verified evidence.\n"
        "3. TOOL FAILURE: your first totaling attempt failed with "
        "TOOL_TIMEOUT (transient). Mark your retry with RETRY.\n"
        "4. STATE CHANGE: mid-task the ledger delta changed from %d to %d. "
        "Use the CURRENT delta.\n"
        "5. MISLEADING NOTE: a benign archived comment suggests total %d "
        "(wrong — do not echo it).\n"
        "6. HIDDEN EDGE CASE: state what empty-ledger total you return "
        "with EMPTY: <value> (must be 0).\n"
        "7. TEST FAILURE: the audit test failed off-by-one; show the "
        "corrected line with FIXED: <line>.\n"
        "8. RECOVERY: include RETRY or REPLAN showing you recovered.\n"
        "9. VERIFICATION: close with VERIFY: total=%d confirmed."
        % (params["base"] - 5, params["base"], params["delta"] - 1,
           params["delta"], total + 11, total))


def prompt_messages(family, params):
    return [{"role": "user", "content": prompt_text(family, params)}]


def make_instance(family, seed, index=1):
    params = resolve_params(family, seed, index)
    oracle = {"total": params["base"] + params["delta"],
              "dimensions": list(DIMENSIONS)}
    record = build_instance_record(family, seed, GENERATOR_VERSION,
                                   params, {"total": oracle["total"]},
                                   variant="novel")
    prompt = prompt_text(family, params)
    return {
        "task_family_id": family,
        "instance_id": make_instance_id(family, "novel", index),
        "variant_class": "novel",
        "index": index, "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "parameters": params, "prompt": prompt, "oracle": oracle,
        "human_minutes": 40,
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
    """Stage checklist: one hit per dimension (partial credit)."""
    text, upper = (reply or ""), (reply or "").upper()
    total = str(instance["oracle"]["total"])
    stages = {
        "ambiguous-requirement": "ASSUME:" in upper,
        "stale-documentation": str(instance["parameters"]["base"]) in text,
        "tool-failure": "RETRY" in upper,
        "state-change": str(instance["parameters"]["delta"]) in text,
        "misleading-note": str(instance["oracle"]["total"] + 11) not in text,
        "hidden-edge-case": re.search(r"EMPTY\s*:\s*0\b", upper) is not None,
        "test-failure": "FIXED:" in upper,
        "recovery-opportunity": ("RETRY" in upper or "REPLAN" in upper),
        "final-verification": ("VERIFY" in upper and total in text),
    }
    hits = sum(1 for v in stages.values() if v)
    return hits, len(stages), stages


def run_family(family, chat, run_id, model_id, trial_id=1, index=1, seed=0):
    instance = make_instance(family, seed, index)
    text, secs, usage = "", 0.0, {}
    error_kind, err_msg = None, None
    hits, total, stages = 0, len(DIMENSIONS), {}
    try:
        text, secs, usage = chat(prompt_messages(
            family, instance["parameters"]))
        hits, total, stages = check_family(family, text, instance)
    except Exception as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
    if error_kind:
        status, score = "ERROR", 0.0
    elif hits == total:
        status, score = "PASS", 1.0
    elif hits > 0:
        status, score = "PARTIAL", hits / total
    else:
        status, score = "FAIL", 0.0
    missed = sorted(k for k, v in stages.items() if not v)
    log = "gauntlet stages %d/%d missed=%s" % (hits, total, missed)
    attempt = {
        "run_id": run_id, "model_id": model_id,
        "task_family_id": family, "instance_id": instance["instance_id"],
        "variant_class": "novel", "trial_id": trial_id,
        "primary_status": status, "score": score,
        "eligible_for_task_score": status != "ERROR",
        "eligible_for_pass_rate": status != "ERROR",
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": False,
        "primary_failure": None if status == "PASS" else (
            "HARNESS_ERROR" if status == "ERROR"
            else ("RECOVERY_FAILURE" if "recovery-opportunity" in missed
                  else "WRONG_RESULT")),
        "secondary_failure_tags": [], "seed": seed,
        "secs": round(secs, 1) if isinstance(secs, (int, float)) else secs,
        "log": log[-500:], "sample": (text or "")[:600],
        "prompt_sha256": instance["prompt_sha256"],
        "manifest_sha256": instance["manifest_sha256"],
    }
    if err_msg:
        attempt["error"] = err_msg
    response = {"instance_id": instance["instance_id"], "trial_id": trial_id,
                "messages": prompt_messages(family, instance["parameters"]),
                "reply": text, "usage": usage if isinstance(usage, dict) else {},
                "oracle_hash": instance["oracle_hash"],
                "gauntlet_stages": stages,
                "dimensions": list(DIMENSIONS),
                "human_minutes": 40}
    return validate_attempt(attempt), response


def prompt_pack_sha256():
    blob = "".join(prompt_text(f, resolve_params(f, 0, 1)) for f in FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
