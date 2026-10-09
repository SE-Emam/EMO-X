"""Real executor for suites/vision (stdlib only). SPEC 36/P6, PLAN 3.4-3.5.

Replaces the PILOT stub with a working executor over
vision-bench/{run_vision.py, fixtures/}: frozen vision-v1 prompts,
deterministic oracles (IoU>=0.5 grounding, keyword Arabic, exact-count),
and the two-stage capability gate (models-hint + mandatory probe image).

Gate semantics (fail-closed, never silent pass):
  - gate passes  -> attempts run normally (PASS/FAIL scored).
  - gate fails   -> every family returns status VOID (not scored),
                   error names the gate cause. The suite NEVER marks a
                   model failed for lacking image support.
  - --force path: caller passes force=True to run anyway; image-call
    failures then become ERROR (infra), never FAIL.

Raw records only (schema-valid per shared/schemas.py C4/C83).
No scoring here (X-3 owns it).
"""

import hashlib
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
VBENCH = os.path.join(ROOT, "vision-bench")
for _p in (HERE, ROOT, SHARED, VBENCH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from schemas import validate_attempt  # noqa: E402
from manifests import sha256_bytes, sha256_manifest  # noqa: E402

SUITE = "vision"
FAMILY_IDS = ("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9")
VARIANTS = ("canonical", "perturbed")

# Sprint 1: exact deterministic family -> test-name map.
# Sprint 2: V7 (multi-image diff), V8 (spatial), V9 (chart) added.
# Replaces brittle startswith + sorted[0] dispatch (routing errors
# impossible: unknown family raises KeyError, ambiguous raises RuntimeError).
FAMILY_TEST_MAP = {
    "V1": "V1_ground_login",
    "V2": "V2_ground_save",
    "V3": "V3_arabic_read",
    "V4": "V4_count_circles",
    "V5": "V5_count_toolbar_buttons",
    "V6": "V6_count_red_squares",
    "V7": "V7_diff_pair",
    "V8": "V8_spatial_above",
    "V9": "V9_chart_red",
}

# Families supporting the perturbed variant (Sprint 1: counting only).
PERTURBED_FAMILIES = ("V4", "V5")


def _load_vbench():
    path = os.path.join(VBENCH, "run_vision.py")
    name = "emox_vision_runner"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_manifest(family):
    """Load suites/vision/manifests/<family>.json."""
    path = os.path.join(HERE, "manifests", "%s.json" % family)
    with open(path, encoding="utf-8") as f:
        import json

        return json.load(f)


def prompt_pack_sha256():
    """SHA256 over frozen vision-v1 prompts + fixture bytes (B58)."""
    vb = _load_vbench()
    # Sprint 1: V1-V6 prompts. Sprint 2: V7/V8/V9 prompts appended
    # (prompts frozen; appending keeps V1-V6 prefix stable).
    parts = [vb.P_GROUND, vb.P_ARABIC, vb.P_COUNT, vb.P_DIFF, vb.P_SPATIAL_AR, vb.P_CHART]
    gt_path = os.path.join(VBENCH, "fixtures", "ground_truth.json")
    with open(gt_path, "rb") as f:
        parts.append(f.read().decode("utf-8"))
    for png in (
        "ui_login.png",
        "ui_toolbar.png",
        "arabic_card.png",
        "grid_count.png",
        "grid_count_perturbed.png",
        "ui_toolbar_perturbed.png",
        "diff_a.png",
        "diff_b.png",
        "spatial.png",
        "chart.png",
    ):
        with open(os.path.join(VBENCH, "fixtures", png), "rb") as f:
            parts.append(hashlib.sha256(f.read()).hexdigest())
    blob = "\n".join(parts)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    """SHA256 of this executor file's bytes (B58 harness hash input)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())


def _gate(chat, base_url, force=False):
    """Two-stage vision gate. Returns None if runnable, else VOID reason.

    Stage 1 (hint): GET {base}/models scan — advisory only.
    Stage 2 (binding): mandatory tiny-image probe call — decisive.
    force=True bypasses the gate (failures then count as ERROR).
    """
    vb = _load_vbench()
    if force:
        return None
    hint = vb.models_hint_supports_vision(base_url or "")
    ok, detail = vb.probe_image_call(chat)
    if ok:
        return None
    if hint is False:
        return "no vision model advertised at /models AND probe image call failed (%s)" % detail
    return "probe image call failed (%s)" % detail


def _void_attempt(family, run_id, model_id, trial_id, reason):
    return validate_attempt(
        {
            "run_id": run_id,
            "model_id": model_id,
            "task_family_id": family,
            "instance_id": "%s-canonical-001" % family,
            "variant_class": "canonical",
            "trial_id": trial_id,
            "primary_status": "VOID",
            "score": 0.0,
            "eligible_for_task_score": False,
            "eligible_for_pass_rate": False,
            "eligible_for_efficiency": False,
            "eligible_for_calibration": False,
            "primary_failure": None,
            "secondary_failure_tags": [],
            "error": "vision-gate: %s" % reason[:250],
        }
    )


def run_family(
    family,
    chat,
    run_id,
    model_id,
    trial_id=1,
    index=1,
    seed=0,
    manifest=None,
    variant=None,
    base_url="",
    force=False,
):
    """Run one vision family. Returns (attempt, response), schema-valid.

    variant None defaults to "canonical". "perturbed" is supported only
    for V4/V5 (Sprint 1 counting robustness); other families raise
    TypeError on perturbed (NA, DEN). Unknown family raises KeyError.
    Gate failure -> VOID attempt (never FAIL/ERROR for the model).
    """
    v = variant or "canonical"
    if family not in FAMILY_IDS:
        raise KeyError("unknown vision family: %r" % (family,))
    if v not in VARIANTS:
        raise TypeError("variant %r not supported for family %r" % (v, family))
    if v == "perturbed" and family not in PERTURBED_FAMILIES:
        raise TypeError("variant %r not supported for family %r" % (v, family))
    vb = _load_vbench()
    reason = _gate(chat, base_url, force)
    if reason is not None:
        attempt = _void_attempt(family, run_id, model_id, trial_id, reason)
        return attempt, {
            "instance_id": attempt["instance_id"],
            "trial_id": trial_id,
            "reply": "",
            "usage": {},
            "void": True,
            "gate": reason,
        }
    gt = vb.load_ground_truth()
    # Sprint 1: exact deterministic dispatch (no startswith/sorted[0]).
    test_name = FAMILY_TEST_MAP[family]
    tests = {name: (img, prompt, target) for name, img, prompt, target in vb.build_tests(gt)}
    if test_name not in tests:
        raise KeyError("no vision test maps to family: %r" % (family,))
    name = test_name
    img, prompt, (kind, target) = tests[name]
    if v == "perturbed":
        pimg = vb.perturbed_image_for(img)
        if pimg is not None:
            img = pimg
        # Count target is UNCHANGED under perturbation (same GT numbers).
    # Sprint 2: V7 carries a [image_a, image_b] list (image_count=2).
    # Route lists via vision_messages_multi + run_one_multi (5MB fail-closed
    # guard inside returns a VOID record, never FAIL/ERROR for the model).
    if isinstance(img, (list, tuple)):
        messages = vb.vision_messages_multi(prompt, list(img))
        try:
            rec = vb.run_one_multi(chat, kind, target, prompt, list(img))
        except Exception as e:
            err = str(e)[:300]
            if vb.NO_IMAGE_RE.search(err):
                attempt = _void_attempt(
                    family, run_id, model_id, trial_id, "endpoint rejects image content: %s" % err
                )
                return attempt, {
                    "instance_id": attempt["instance_id"],
                    "trial_id": trial_id,
                    "reply": "",
                    "usage": {},
                    "void": True,
                    "gate": err,
                }
            raise
        if rec.get("void"):
            attempt = _void_attempt(
                family,
                run_id,
                model_id,
                trial_id,
                str(rec.get("log", "multi-image payload too large")),
            )
            return attempt, {
                "instance_id": attempt["instance_id"],
                "trial_id": trial_id,
                "reply": "",
                "usage": rec.get("usage") if isinstance(rec.get("usage"), dict) else {},
                "void": True,
                "gate": rec.get("log", ""),
            }
    else:
        messages = vb.vision_messages(prompt, img)
        try:
            rec = vb.run_one(chat, kind, target, prompt, img)
        except Exception as e:
            err = str(e)[:300]
            if vb.NO_IMAGE_RE.search(err):
                attempt = _void_attempt(
                    family, run_id, model_id, trial_id, "endpoint rejects image content: %s" % err
                )
                return attempt, {
                    "instance_id": attempt["instance_id"],
                    "trial_id": trial_id,
                    "reply": "",
                    "usage": {},
                    "void": True,
                    "gate": err,
                }
            raise
    passed = bool(rec.get("pass"))
    # Sprint 1: INVALID (no parseable int) vs WRONG_RESULT (+off_by_1 tag).
    if passed:
        status, failure = "PASS", None
    elif rec.get("invalid"):
        status, failure = "INVALID", "INVALID_NO_INT"
    elif rec.get("off_by_one"):
        status, failure = "FAIL", "WRONG_RESULT (off_by_1)"
    else:
        status, failure = "FAIL", "WRONG_RESULT"
    attempt = validate_attempt(
        {
            "run_id": run_id,
            "model_id": model_id,
            "task_family_id": family,
            "instance_id": "%s-%s-%03d" % (family, v, index),
            "variant_class": v,
            "trial_id": trial_id,
            "primary_status": status,
            "score": 1.0 if passed else 0.0,
            "eligible_for_task_score": True,
            "eligible_for_pass_rate": True,
            "eligible_for_efficiency": True,
            "eligible_for_calibration": False,
            "primary_failure": failure,
            "secondary_failure_tags": [],
            "seed": seed,
            "reasoning_mode": "provider_default",
            "log": str(rec.get("log", ""))[:500],
            "sample": str(rec.get("sample", ""))[:600],
            "manifest_sha256": sha256_manifest(manifest or load_manifest(family)),
        }
    )
    response = {
        "instance_id": attempt["instance_id"],
        "trial_id": trial_id,
        "messages": messages,
        "reply": rec.get("sample", ""),
        "usage": rec.get("usage") if isinstance(rec.get("usage"), dict) else {},
        "vision_log": rec.get("log", ""),
    }
    return attempt, response
