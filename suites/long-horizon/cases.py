"""EMO-X long-horizon suite: L1-L5 chained primitives (X-5, WP13).

SPEC 25: long tasks compose previously validated primitives
(inspect -> plan -> modify -> test -> diagnose -> repair -> refactor ->
verify -> final report). Levels L1 (5 checkpoints) through L5 (12
checkpoints) carry estimated_human_minutes (SPEC 26: 5/10/20/40/80).

Each checkpoint is a deterministic micro-computation chained on the
previous answer, so error accumulates with horizon (SPEC 25: step
survival, error accumulation). Partial credit uses the checkpoint
weights (SPEC B4: PASS all / PARTIAL some / FAIL none). Time-horizon
fitting (B46) consumes the human-minutes labels downstream.
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
from generators.seeds import (GENERATOR_VERSION, make_rng,  # noqa: E402
                              make_instance_id, build_instance_record)

SUITE = "long-horizon"
FAMILY_IDS = ("LH1", "LH2", "LH3", "LH4", "LH5")

CHECKPOINTS = {"LH1": 5, "LH2": 6, "LH3": 8, "LH4": 10, "LH5": 12}
HUMAN_MINUTES = {"LH1": 5, "LH2": 10, "LH3": 20, "LH4": 40, "LH5": 80}


def resolve_params(family, seed, index=1):
    rng = make_rng(seed * 90007 + index, GENERATOR_VERSION)
    return {"start": rng.randint(2, 50), "step": rng.randint(2, 9)}


def chain_values(params, n):
    """Chained primitive values: v[0]=start, v[k]=v[k-1]+step+k."""
    vals = [params["start"]]
    for k in range(1, n):
        vals.append(vals[-1] + params["step"] + k)
    return vals


def prompt_text(family, params):
    n = CHECKPOINTS[family]
    lines = ["Long-horizon chain (%d checkpoints). Start: %d, rule: add "
             "%d then add the checkpoint number." % (n, params["start"],
                                                    params["step"])]
    for k in range(n):
        lines.append("Checkpoint C%d: current value?" % (k + 1))
    lines.append("Reply with one line per checkpoint: C1: <v> ... C%d: <v>."
                 % n)
    return "\n".join(lines)


def prompt_messages(family, params):
    return [{"role": "user", "content": prompt_text(family, params)}]


def make_instance(family, seed, index=1):
    params = resolve_params(family, seed, index)
    n = CHECKPOINTS[family]
    oracle = {"values": chain_values(params, n),
              "human_minutes": HUMAN_MINUTES[family],
              "n_checkpoints": n}
    record = build_instance_record(family, seed, GENERATOR_VERSION,
                                   params, {"values": oracle["values"]},
                                   variant="canonical")
    prompt = prompt_text(family, params)
    return {
        "task_family_id": family,
        "instance_id": make_instance_id(family, "canonical", index),
        "variant_class": "canonical",
        "index": index, "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "parameters": params, "prompt": prompt, "oracle": oracle,
        "human_minutes": HUMAN_MINUTES[family],
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
    """Checkpoint scoring: fraction of correct chain values (B4-style)."""
    expected = instance["oracle"]["values"]
    found = {}
    for m in re.finditer(r"C\s*(\d+)\s*:\s*(-?\d+)", reply or ""):
        try:
            found[int(m.group(1))] = int(m.group(2))
        except ValueError:
            continue
    hits = sum(1 for k, v in enumerate(expected, start=1)
               if found.get(k) == v)
    return hits, len(expected)


def run_family(family, chat, run_id, model_id, trial_id=1, index=1, seed=0):
    instance = make_instance(family, seed, index)
    text, secs, usage = "", 0.0, {}
    error_kind, err_msg = None, None
    hits, total = 0, CHECKPOINTS[family]
    try:
        text, secs, usage = chat(prompt_messages(
            family, instance["parameters"]))
        hits, total = check_family(family, text, instance)
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
    log = "checkpoints %d/%d (human_minutes=%d)" % (
        hits, total, HUMAN_MINUTES[family])
    attempt = {
        "run_id": run_id, "model_id": model_id,
        "task_family_id": family, "instance_id": instance["instance_id"],
        "variant_class": "canonical", "trial_id": trial_id,
        "primary_status": status, "score": score,
        "eligible_for_task_score": status != "ERROR",
        "eligible_for_pass_rate": status != "ERROR",
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": False,
        "primary_failure": None if status == "PASS" else (
            "HARNESS_ERROR" if status == "ERROR"
            else ("WRONG_RESULT" if status == "FAIL" else None)),
        "secondary_failure_tags": [], "seed": seed,
        "secs": round(secs, 1) if isinstance(secs, (int, float)) else secs,
        "log": log, "sample": (text or "")[:600],
        "prompt_sha256": instance["prompt_sha256"],
        "manifest_sha256": instance["manifest_sha256"],
    }
    if err_msg:
        attempt["error"] = err_msg
    response = {"instance_id": instance["instance_id"], "trial_id": trial_id,
                "messages": prompt_messages(family, instance["parameters"]),
                "reply": text, "usage": usage if isinstance(usage, dict) else {},
                "oracle_hash": instance["oracle_hash"],
                "checkpoints": {"hits": hits, "total": total},
                "human_minutes": HUMAN_MINUTES[family]}
    return validate_attempt(attempt), response


def prompt_pack_sha256():
    blob = "".join(prompt_text(f, resolve_params(f, 0, 1)) for f in FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
