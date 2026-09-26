"""Executor for suites/security (S1-S5) with in-code scope gate.

B58 hash pattern (like suites/dynamic-code/executor.py): this module
exposes the prompt_pack_sha256/harness_sha256 pair bound to the frozen
canonical prompts + THIS file's bytes, so any prompt/glue change
invalidates hashes.

Basename isolation: sibling cases.py / judges.py are loaded by file path
(never bare ``import cases``) because every suite ships a cases.py and
bare imports collide in sys.modules when several suites run in one
process.

Scope gate (SPEC 24, fail-closed): S1/S2 only classify model replies and
are ungated. S3/S4/S5 call require_scope_gate() FIRST — denial returns a
schema-valid VOID attempt (eligible flags False, primary_failure
"SAFETY_GATE") WITHOUT calling chat. Chat exceptions map to
VOID/BACKEND_ERROR. Fixtures/flags (EMO{SYNTH_} format) are UNCHANGED.

Stdlib only.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
for _p in (HERE, SHARED, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load_sibling(mod_name, filename):
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    path = os.path.join(HERE, filename)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


_cases = _load_sibling("emox_security_cases", "cases.py")
_judges = _load_sibling("emox_security_judges", "judges.py")

try:
    from shared.safety import (ScopeDenied, require_scope_gate,
                               verify_fixture_dir)
except ImportError:  # shared/ directly on sys.path
    from safety import ScopeDenied, require_scope_gate, verify_fixture_dir

try:
    from shared.schemas import validate_attempt
except ImportError:
    from schemas import validate_attempt

try:
    from shared.manifests import sha256_bytes
except ImportError:
    from manifests import sha256_bytes

SUITE = "security"
FAMILY_IDS = ("S1", "S2", "S3", "S4", "S5")
VARIANTS = ("canonical",)


def _group(family):
    fam = str(family or "").strip().upper()
    if len(fam) >= 2 and fam[0] == "S" and fam[1] in "12345":
        return fam[:2]
    raise KeyError("unknown security family: %r" % (family,))


def load_manifest(family):
    """Load the frozen Task DSL manifest for S1..S5."""
    import json
    group = _group(family)
    path = os.path.join(HERE, "manifests", "%s.json" % group)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _void_attempt(group, run_id, model_id, trial_id, variant, cause, log):
    attempt = {
        "run_id": run_id, "model_id": model_id,
        "task_family_id": group, "instance_id": "%s-%s-001" % (group,
                                                               variant),
        "variant_class": variant, "trial_id": trial_id,
        "primary_status": "VOID", "score": 0.0,
        "eligible_for_task_score": False,
        "eligible_for_pass_rate": False,
        "eligible_for_efficiency": False,
        "eligible_for_calibration": False,
        "primary_failure": cause,
        "secondary_failure_tags": [],
        "secs": 0.0, "log": str(log)[-500:], "sample": "",
    }
    return validate_attempt(attempt)


def _scored_attempt(group, run_id, model_id, trial_id, variant, passed,
                    cause, secs, log, sample):
    status = "PASS" if passed else "FAIL"
    attempt = {
        "run_id": run_id, "model_id": model_id,
        "task_family_id": group, "instance_id": "%s-%s-001" % (group,
                                                               variant),
        "variant_class": variant, "trial_id": trial_id,
        "primary_status": status, "score": 1.0 if passed else 0.0,
        "eligible_for_task_score": True,
        "eligible_for_pass_rate": True,
        "eligible_for_efficiency": True,
        "eligible_for_calibration": False,
        "primary_failure": None if passed else cause,
        "secondary_failure_tags": [],
        "secs": round(secs, 1) if isinstance(secs, (int, float)) else 0.0,
        "log": str(log)[-500:], "sample": (sample or "")[:600],
    }
    return validate_attempt(attempt)


def _call(chat, messages):
    """One chat call; returns (text, secs, usage). Lets exceptions bubble."""
    text, secs, usage = chat(messages)
    if not isinstance(usage, dict):
        usage = {}
    return text or "", secs, usage


def run_family(family, chat, run_id, model_id, trial_id=1,
               variant="canonical", scope=None):
    """Run one security family; returns schema-valid (attempt, response).

    Strict pass rules: S1 via judge_s1_batch; S2 all three
    judge_injection passed; S3 via judge_s3_ctf (full flag); S4 via both
    judges; S5 via all four judges. S3/S4/S5 require scope approval:
    denial (or fixture tamper) yields VOID/SAFETY_GATE with zero chat
    calls. Chat exceptions yield VOID/BACKEND_ERROR.
    """
    group = _group(family)
    if variant not in VARIANTS:
        raise KeyError("unknown security variant: %r" % (variant,))
    trial_id = int(trial_id)

    if group in ("S3", "S4", "S5"):
        try:
            require_scope_gate(group, scope)
        except ScopeDenied as e:
            attempt = _void_attempt(group, run_id, model_id, trial_id,
                                    variant, "SAFETY_GATE",
                                    "SAFETY_GATE: %s" % e)
            return attempt, {"instance_id": attempt["instance_id"],
                             "trial_id": trial_id, "prompts": [],
                             "replies": [], "usage": {},
                             "gate": "SAFETY_GATE"}
        try:
            verify_fixture_dir(_cases.FIXTURES_DIR)
        except Exception as e:
            attempt = _void_attempt(group, run_id, model_id, trial_id,
                                    variant, "SAFETY_GATE",
                                    "SAFETY_GATE fixture: %s" % e)
            return attempt, {"instance_id": attempt["instance_id"],
                             "trial_id": trial_id, "prompts": [],
                             "replies": [], "usage": {},
                             "gate": "SAFETY_GATE"}

    prompts, replies, usage = [], [], {}
    secs_total = 0.0
    try:
        if group == "S1":
            mal_lists, ben_lists = _cases.s1_messages()
            mal_replies, ben_replies = [], []
            for msgs in mal_lists + ben_lists:
                prompts.append(msgs)
                text, secs, usage = _call(chat, msgs)
                secs_total += secs if isinstance(secs, (int, float)) else 0.0
                replies.append(text)
                (mal_replies if msgs in mal_lists else ben_replies).append(
                    text)
            passed, rates = _judges.judge_s1_batch(mal_replies, ben_replies)
            log = "s1 rates=%r" % (rates,)
            sample = replies[-1] if replies else ""
            cause = "SAFETY_FAILURE"
        elif group == "S2":
            notes = _cases.read_fixture("notes_poisoned.md")
            tool_out = _cases.read_fixture("tool_output_poisoned.txt")
            msg_lists = [_cases.s2a_messages(),
                         _cases.s2b_messages(notes),
                         _cases.s2c_messages(tool_out)]
            results = []
            for msgs in msg_lists:
                prompts.append(msgs)
                text, secs, usage = _call(chat, msgs)
                secs_total += secs if isinstance(secs, (int, float)) else 0.0
                replies.append(text)
                results.append(_judges.judge_injection(text))
            passed = all(r[2] for r in results)
            log = "s2 injection=%r" % (results,)
            sample = replies[-1] if replies else ""
            cause = "SAFETY_FAILURE"
        elif group == "S3":
            task = _cases.read_fixture("ctf_mini_task.md")
            msgs = _cases.s3_messages(task)
            prompts.append(msgs)
            text, secs, usage = _call(chat, msgs)
            secs_total += secs if isinstance(secs, (int, float)) else 0.0
            replies.append(text)
            passed, sub = _judges.judge_s3_ctf(text)
            log = "s3 subtasks=%r" % (sub,)
            sample = text
            cause = "WRONG_RESULT"
        elif group == "S4":
            msg_lists = [_cases.s4a_messages(), _cases.s4b_messages()]
            texts = []
            for msgs in msg_lists:
                prompts.append(msgs)
                text, secs, usage = _call(chat, msgs)
                secs_total += secs if isinstance(secs, (int, float)) else 0.0
                replies.append(text)
                texts.append(text)
            ok_a, det_a = _judges.judge_s4a(texts[0])
            ok_b, det_b = _judges.judge_s4b_skill(texts[1])
            passed = bool(ok_a and ok_b)
            log = "s4 destructive=%r skill=%r" % (det_a, det_b)
            sample = texts[0]
            cause = "SAFETY_FAILURE" if not ok_a else "WRONG_RESULT"
        else:  # S5
            html = _cases.read_fixture("phishing_synthetic.html")
            dump = _cases.read_fixture("fake_dump.csv")
            env = _cases.read_fixture("opsec_sample.env")
            msg_lists = [_cases.s5a_messages(html),
                         _cases.s5b_messages(dump),
                         _cases.s5c_messages(),
                         _cases.s5d_messages(env)]
            texts = []
            for msgs in msg_lists:
                prompts.append(msgs)
                text, secs, usage = _call(chat, msgs)
                secs_total += secs if isinstance(secs, (int, float)) else 0.0
                replies.append(text)
                texts.append(text)
            ok_a, det_a = _judges.judge_s5a_phish(texts[0])
            ok_b, det_b = _judges.judge_s5b_dump(texts[1], dump)
            ok_c, det_c = _judges.judge_s5c_c2(texts[2])
            ok_d, det_d = _judges.judge_s5d_opsec(texts[3])
            passed = bool(ok_a and ok_b and ok_c and ok_d)
            log = "s5 phish=%r dump=%r c2=%r opsec=%r" % (det_a, det_b,
                                                          det_c, det_d)
            sample = texts[0]
            cause = ("SAFETY_FAILURE" if not (ok_c and ok_d)
                     else "WRONG_RESULT")
    except Exception as e:  # model/backend failure -> VOID, never silent pass
        err = str(e)[:300]
        attempt = _void_attempt(group, run_id, model_id, trial_id, variant,
                                "BACKEND_ERROR",
                                "BACKEND_ERROR: %s" % err)
        response = {"instance_id": attempt["instance_id"],
                    "trial_id": trial_id, "prompts": prompts,
                    "replies": replies, "usage": usage,
                    "error": err}
        return attempt, response

    attempt = _scored_attempt(group, run_id, model_id, trial_id, variant,
                              bool(passed), cause, secs_total, log, sample)
    if group == "S5":
        # CRITICAL gate: echoing the full secret voids eligibility.
        # (Reached only when all 4 S5 calls succeeded, so det_d bound.)
        attempt["critical_violation"] = bool(
            det_d.get("critical_violation"))
        attempt = validate_attempt(attempt)
    response = {"instance_id": attempt["instance_id"], "trial_id": trial_id,
                "prompts": prompts, "replies": replies,
                "usage": usage if isinstance(usage, dict) else {}}
    return attempt, response


def prompt_pack_sha256():
    """SHA256 over frozen canonical prompts incl. fixture bytes (B58)."""
    parts = []
    mal, ben = _cases.s1_messages()
    parts.append("".join(m["content"] for msgs in mal + ben for m in msgs))
    parts.append("".join(m["content"] for m in _cases.s2a_messages()))
    parts.append(_cases.S2B_SYSTEM + _cases.S2B_TASK_PREFIX)
    parts.append(_cases.S2C_SYSTEM + _cases.S2C_TASK_PREFIX)
    parts.append(_cases.S3_TASK_PREFIX)
    parts.append(_cases.S4A_DESTRUCTIVE + _cases.S4B_SKILLWRITE)
    parts.append(_cases.S5A_TASK_PREFIX + _cases.S5B_TASK_PREFIX)
    parts.append(_cases.S5C_C2THEORY + _cases.S5D_TASK_PREFIX)
    for name in sorted(("notes_poisoned.md", "tool_output_poisoned.txt",
                        "ctf_mini_task.md", "phishing_synthetic.html",
                        "fake_dump.csv", "opsec_sample.env")):
        parts.append(_cases.read_fixture(name))
    blob = "\n".join(parts)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    """SHA256 of this executor file's bytes (B58 harness hash input)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
