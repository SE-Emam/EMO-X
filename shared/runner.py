"""EMO-X unified suite runner (X-5, WP15). SPEC sections 32-33, 35, 42.

Owns suite orchestration, manifest construction, the offline stub chat,
the fail-closed harness self-test (SPEC 35), and the benchmark-health
entry point (--health). Bundle persistence and host metadata collection
live in shared/bundles.py and shared/environment.py; public compatibility
names remain available here.

Conventions (binding): NA is None; missing eligibility flags default
True; aggregation Attempt->Instance->Variant->Task->Capability imports
shared.denominators / shared.scoring, never reinvented. B58: any
prompt/glue change invalidates hashes (hashes come from each suite's
executor helpers, following X-4's prompt_pack_sha256/harness_sha256
pattern).

Stdlib only. English code.
"""

import datetime
import hashlib
import importlib.util
import json
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from manifests import sha256_bytes, verify_prompt_pack  # noqa: E402
from schemas import (  # noqa: E402
    VoidRun,
    classify_cause,
    validate_attempt,
    validate_run_manifest,
)

try:
    from bundles import BundleStream, write_raw_bundle
    from environment import _git_sha, collect_hardware, collect_toolchain
except ImportError:
    from shared.bundles import BundleStream
    from shared.environment import _git_sha, collect_hardware, collect_toolchain

#: Prompt-pack verification per suite entry point (VOID on tamper, Y-1).
#: code25 prompts live frozen in shared/PROMPT_PACK_v1.md.
SUITE_PROMPT_PACK = {"code25": "PROMPT_PACK_v1"}

BENCHMARK_VERSION = "2.0.0-rc1"
RUNNER_VERSION = "2.0.0-rc1"

#: Suites executable through this runner (code25 reuses X-4's executor).
SUITE_DIRS = {
    "code25": "code-bench-25",
    "agent-loop": "agent-loop",
    "code25-hidden": "code-bench-25-hidden",
    "security": "security",
    "dynamic-code": "dynamic-code",
    "recovery": "recovery",
    "robustness": "robustness",
    "calibration": "calibration",
    "long-horizon": "long-horizon",
    "gauntlet": "gauntlet",
    "vision": "vision",
    "realworld": "realworld",
    "issues": "issues",
}

#: Claim tier per suite (overfitting defense, Y-4). Hidden validation
#: suites never contribute to public claims.
SUITE_CLAIM_TIER = {"code25-hidden": "HIDDEN-VALIDATION"}
DEFAULT_CLAIM_TIER = "PUBLIC-BENCHMARK"

#: Required model modality per suite (model-level capability gate).
#: Every suite today needs text generation except vision (image input).
#: An embedding-only (or audio-only) model run against any suite below
#: is REFUSED before the first model call — scored zeros from an
#: incapable model are inadmissible, never measured.
SUITE_MODALITIES = {
    "vision": "vision",
}
DEFAULT_SUITE_MODALITY = "text"

#: Full capability profile (SPEC 42 --suite profile).
PROFILE_SUITES = (
    "code25",
    "dynamic-code",
    "recovery",
    "robustness",
    "calibration",
    "long-horizon",
    "gauntlet",
)

_executor_cache = {}

#: Cache for manifest human-minutes lookups (SPEC 26 lite).
_minutes_cache = {}


def manifest_minutes(suite, family):
    """estimated_human_minutes for a family, or None. SPEC 26 lite.

    Single source of truth: suites/<dir>/manifests/<family>.json
    (agent-loop uses manifest.json). Missing file/field => None (NA).
    """
    key = (suite, family)
    if key not in _minutes_cache:
        mins = None
        try:
            directory = SUITE_DIRS.get(suite)
            if directory:
                base = os.path.join(ROOT, "suites", directory)
                cand = [
                    os.path.join(base, "manifests", family + ".json"),
                    os.path.join(base, "manifest.json"),
                ]
                for path in cand:
                    if os.path.isfile(path):
                        with open(path, encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, dict) and isinstance(
                            data.get("estimated_human_minutes"), (int, float)
                        ):
                            mins = data["estimated_human_minutes"]
                        break
        except Exception:
            mins = None
        _minutes_cache[key] = mins
    return _minutes_cache[key]


def load_executor(suite):
    """Load a suite executor by file path (unique module name per suite).

    Basename isolation: every suite ships cases.py/executor.py, so plain
    imports would collide in sys.modules (the same root cause as
    tests/run_all.py). Loading by path with a per-suite module name keeps
    each suite's globals separate.
    """
    if suite not in SUITE_DIRS:
        raise ValueError(
            "unknown suite: {!r} (choose from {}, profile)".format(
                suite, ", ".join(sorted(SUITE_DIRS))
            )
        )
    if suite not in _executor_cache:
        path = os.path.join(ROOT, "suites", SUITE_DIRS[suite], "executor.py")
        name = "emox_exec_{}".format(SUITE_DIRS[suite].replace("-", "_"))
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load suite executor: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _executor_cache[suite] = module
    return _executor_cache[suite]


def load_cases(suite):
    """Load a suite's cases.py by file path (same isolation as executor)."""
    if suite not in SUITE_DIRS:
        raise ValueError(f"unknown suite: {suite!r}")
    path = os.path.join(ROOT, "suites", SUITE_DIRS[suite], "cases.py")
    name = "emox_cases_{}".format(SUITE_DIRS[suite].replace("-", "_"))
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load suite cases: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def suite_families(suite, executor):
    """Family ids for a suite (executor or its cases module)."""
    families = getattr(executor, "FAMILY_IDS", None)
    if families is None:
        families = load_cases(suite).FAMILY_IDS
    return list(families)


def stub_chat_factory(note="stub"):
    """Deterministic offline chat for smoke e2e (no network, no model).

    Always returns a fixed non-passing reply. Attempts still form a
    schema-valid raw bundle (FAIL is a scored status), which is all an
    infrastructure smoke run needs. Never used for official numbers.
    """

    def chat(messages, **kwargs):
        text = (
            f"STUB-REPLY ({note}): no model attached; "
            "this run validates harness plumbing only."
        )
        return text, 0.0, {"stub": True}

    return chat


def make_run_id(prefix="RUN"):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    digest = hashlib.sha256(os.urandom(16)).hexdigest()[:10]
    return "%s-%s-%s-p%d" % (prefix, stamp, digest, os.getpid())


def build_manifest(
    suite,
    prompt_sha256,
    harness_sha256,
    model,
    backend,
    seed,
    trials,
    run_id,
    extra=None,
    provider_profile=None,
    backend_capabilities=None,
    sampling=None,
    timestamp_utc=None,
    model_modalities=None,
    model_type=None,
):
    """SPEC 32 run manifest (validated; B58 hashes are real, not stubbed).

    SPEC 36: the backend capability manifest is recorded on every run so
    API differences can never be mistaken for model differences. Resolved
    lazily via backends.get_capability_manifest() unless explicitly given.

    Model modalities (model-level capabilities, distinct from backend
    capabilities) are recorded from model_modalities ("text,vision" or
    list; default text-only) so a reader can verify the model was
    capable of the suite at all.

    Rebuild rule: the manifest must contain everything needed to recreate
    the run except the model weights themselves (sampling params, seeds,
    hashes, toolchain, platform). Unknown values are recorded as
    "unknown", never guessed.
    """
    if backend_capabilities is None:
        try:
            from backends import get_capability_manifest
        except ImportError:  # pragma: no cover - path fallback (X-2 pattern)
            from shared.backends import get_capability_manifest
        try:
            backend_capabilities = get_capability_manifest(backend, provider_profile)
        except ValueError:
            # Non-model backends (e.g. "stub" smoke runs): record an
            # all-unknown manifest instead of crashing. Such runs are
            # plumbing-only and never official (SPEC 36).
            from backends import CAPABILITY_FIELDS

            backend_capabilities = dict.fromkeys(CAPABILITY_FIELDS, "unknown")
            backend_capabilities["backend"] = backend
            backend_capabilities["provider_profile"] = "stub"
    sampling = dict(sampling or {})
    try:
        _device_class_value = collect_hardware().get("device_class", "unknown")
    except Exception:
        _device_class_value = "unknown"
    if not isinstance(_device_class_value, str) or not _device_class_value.strip():
        _device_class_value = "unknown"
    manifest = {
        "benchmark_version": BENCHMARK_VERSION,
        "suite": suite,
        "prompt_pack": "PROMPT_PACK_v2" if suite != "code25" else "PROMPT_PACK_v1",
        "prompt_sha256": prompt_sha256,
        "harness_sha256": harness_sha256,
        "harness_git_sha": _git_sha(),
        "backend": backend,
        "provider_profile": (
            provider_profile or backend_capabilities.get("provider_profile")
        ),
        "backend_capabilities": backend_capabilities,
        "model": model,
        "model_sha256": sha256_bytes(("model:" + str(model)).encode()),
        "temperature": sampling.get("temperature", 0.4),
        "top_p": sampling.get("top_p"),
        "top_k": sampling.get("top_k"),
        "context": sampling.get("context"),
        "seed": seed,
        "trials": trials,
        "run_id": run_id,
        "hardware": _device_class_value,
        "model_modalities": _manifest_modalities(model_modalities),
        "model_type": (str(model_type).strip().lower() if model_type else None),
        "timestamp_utc": (
            timestamp_utc or datetime.datetime.now(datetime.timezone.utc).isoformat()
        ),
        "runner_version": RUNNER_VERSION,
    }
    if extra:
        for key, value in extra.items():
            if key != "hardware":
                manifest[key] = value
        # Schema already allows a hardware field (RUN_MANIFEST_OPTIONAL,
        # verified in shared/schemas.py — not duplicated here): an
        # explicit non-empty caller value wins over the probe default.
        if isinstance(extra.get("hardware"), str) and extra["hardware"].strip():
            manifest["hardware"] = extra["hardware"].strip()
    return validate_run_manifest(manifest)


def _manifest_modalities(spec):
    """Sorted modality list for the manifest; default text-only."""
    try:
        from safety import parse_model_modalities
    except ImportError:
        from shared.safety import parse_model_modalities
    try:
        return sorted(parse_model_modalities(spec))
    except ValueError:
        return ["text"]


def collect_environment():
    """environment.json payload (SPEC 33)."""
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "runner_version": RUNNER_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "toolchain": collect_toolchain(),
        "hardware": collect_hardware(),
        "harness_git_sha": _git_sha(),
        "written_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def _void_attempt(
    run_id, model_id, family, instance_id, variant, trial_id, cause, detail
):
    """Schema-valid VOID attempt for round-level failures (Y-1).

    cause: one of STATUS_CAUSES keys (classify_cause maps to VOID/ERROR).
    Eligible flags False: never model blame, never scored.
    """
    status = classify_cause(cause)
    attempt = {
        "run_id": run_id,
        "model_id": model_id,
        "task_family_id": family,
        "instance_id": instance_id,
        "variant_class": variant,
        "trial_id": trial_id,
        "primary_status": status,
        "score": 0.0,
        "eligible_for_task_score": False,
        "eligible_for_pass_rate": False,
        "eligible_for_efficiency": False,
        "eligible_for_calibration": False,
        "primary_failure": None,
        "secondary_failure_tags": [],
        "error": str(detail)[:300],
    }
    return validate_attempt(attempt)


def _supported_params(fn):
    """Accepted kwarg names for an executor run_family, plus '*' for **kw.

    Signature mismatches are resolved BEFORE calling (instead of the old
    try/except-TypeError chain, which could misread an internal TypeError
    as a signature mismatch and let fallback TypeErrors escape).
    """
    import inspect

    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return {"*"}
    names = set(sig.parameters)
    for p in sig.parameters.values():
        if p.kind == inspect.Parameter.VAR_KEYWORD:
            names.add("*")
    return names


def _filter_kwargs(fn, kwargs):
    supported = _supported_params(fn)
    if "*" in supported:
        return dict(kwargs)
    return {k: v for k, v in kwargs.items() if k in supported}


def _family_variants(executor, family):
    variants = getattr(executor, "VARIANTS", ("canonical",))
    return list(variants)


def _run_suite_loop(
    executor,
    suite,
    chat,
    model_id,
    backend,
    seed,
    instances,
    trials,
    fault_rate,
    fams,
    run_id,
    provider_profile,
    scope,
    sampling,
    prog,
    attempts,
    responses,
    stream,
    force=False,
):
    """Attempt loop with per-attempt streaming (Phase 3)."""
    for index in range(1, max(instances, 1) + 1):
        for family in fams:
            variants = _family_variants(executor, family)
            for trial in range(1, max(trials, 1) + 1):
                # One attempt per (family, instance, variant, trial).
                for variant in variants:
                    title = family
                    if variant and variant != "canonical":
                        title += " " + str(variant)
                    title += " trial %d/%d" % (trial, max(trials, 1))
                    if max(instances, 1) > 1:
                        title += " · inst %d/%d" % (index, max(instances, 1))
                    prog.start_attempt(title)
                    kwargs = {
                        "run_id": run_id,
                        "model_id": model_id,
                        "trial_id": trial,
                        "index": index,
                        "seed": seed,
                        "scope": scope,
                    }
                    # Variant-aware executors must RECEIVE the loop
                    # variant (DEN C4: distinct variants need distinct
                    # instance_ids; without this every variant ran as
                    # canonical and emitted duplicate C4 identities).
                    if "variant" in _supported_params(executor.run_family):
                        kwargs["variant"] = variant
                    try:
                        # code25-style executors take no variant kwarg:
                        # skip non-canonical variants (missing => NA, DEN).
                        if (
                            "variant" not in _supported_params(executor.run_family)
                            and variant != "canonical"
                        ):
                            continue
                        call_kwargs = _filter_kwargs(executor.run_family, kwargs)
                        # Recovery executor honors fault_rate explicitly.
                        if suite == "recovery" and "fault_rate" in _supported_params(
                            executor.run_family
                        ):
                            call_kwargs["fault_rate"] = fault_rate
                        # Vision executor honors force explicitly
                        # (bypass capability gate; failures then ERROR).
                        if "force" in _supported_params(executor.run_family):
                            call_kwargs["force"] = force
                        attempt, response = executor.run_family(
                            family, chat, **call_kwargs
                        )
                    except Exception as e:
                        # Scope refusals are round-level errors, not VOID
                        # attempts (Y-4/Y-7: no bundle, clean CLI error).
                        if type(e).__name__ in ("ScopeRequiredError", "ScopeDenied"):
                            raise
                        # Unsupported variant => NA (DEN): absent, not an
                        # attempt. Emitting VOID here would corrupt the
                        # coverage denominator with non-attempts.
                        msg = str(e)
                        if (
                            type(e).__name__ == "TypeError"
                            and "not supported for family" in msg
                        ):
                            prog.finish_attempt("SKIPPED-NA")
                            continue
                        # Fail-open rounds are forbidden: record VOID and
                        # continue (Y-1 cause table decides VOID vs ERROR).
                        cause = (
                            "backend-unavailable"
                            if "chat" in type(e).__name__.lower()
                            or "urlopen" in msg
                            or "URLError" in msg
                            or "Timeout" in type(e).__name__
                            else "harness-bug"
                        )
                        attempt = _void_attempt(
                            run_id,
                            model_id,
                            family,
                            "%s-%s-%05d" % (family, variant, index),
                            variant,
                            trial,
                            cause,
                            f"{type(e).__name__}: {msg}",
                        )
                        response = {
                            "instance_id": attempt["instance_id"],
                            "trial_id": trial,
                            "reply": "",
                            "usage": {},
                            "void": True,
                        }
                    attempts.append(attempt)
                    prog.finish_attempt(attempt.get("primary_status", "UNKNOWN"))
                    if response.get("human_minutes") is None:
                        mins = manifest_minutes(suite, family)
                        if mins is not None:
                            response["human_minutes"] = mins
                    responses.append(response)
                    stream.append(attempt, response)


def run_suite(
    suite,
    chat,
    model_id="stub-model",
    backend="stub",
    seed=0,
    instances=1,
    trials=1,
    fault_rate=0.25,
    out_root=None,
    families=None,
    run_id=None,
    provider_profile=None,
    scope=None,
    sampling=None,
    progress=None,
    force=False,
    model_modalities=None,
    model_type=None,
):
    """Run one suite end-to-end and write the raw bundle. SPEC 32-33, 42.

    instances: canonical instances per family (index 1..N).
    trials: repeated trials per instance (trial_id 1..N).
    fault_rate: recovery-suite injection rate (ignored elsewhere).
    scope: forwarded to scope-gated executors (hidden/security).
      Hidden suites refuse without scope "hidden-ok" BEFORE any model
      call (Y-4); the refusal surfaces as a clean error, not a bundle.
    model_modalities: declared model capabilities ("text,vision" or
      list; default text-only). Suites require a modality
      (SUITE_MODALITIES, default text); mismatch raises
      ModelCapabilityDenied BEFORE any model call, with no bundle —
      scored zeros from an incapable model are inadmissible.
    Returns (run_dir, summary_dict).

    Failure contract (Y-1): unexpected per-attempt exceptions become VOID
    attempts (backend-unavailable for chat errors, harness-bug for glue
    errors) and the round continues; a tampered frozen prompt pack aborts
    the whole round as VOID with no partial bundle.
    """
    executor = load_executor(suite)
    try:
        from safety import (
            ModelCapabilityDenied,
            parse_model_modalities,
            require_model_modality,
        )
    except ImportError:
        from shared.safety import (
            parse_model_modalities,
            require_model_modality,
        )
    declared = parse_model_modalities(model_modalities)
    require_model_modality(
        suite, SUITE_MODALITIES.get(suite, DEFAULT_SUITE_MODALITY), declared
    )
    if model_type is not None:
        try:
            from safety import stages_for_type
        except ImportError:
            from shared.safety import stages_for_type
        stages_for_type(model_type)  # unknown/out-of-scope raises here
    pack = SUITE_PROMPT_PACK.get(suite)
    if pack is not None:
        try:
            verify_prompt_pack(pack)  # prompt-tamper => VOID, never scored
        except VoidRun as e:
            raise VoidRun(f"round VOID: {e}")
    # Hidden suites refuse BEFORE any model call, with no bundle (Y-4).
    hidden_gate = getattr(executor, "require_hidden_scope", None)
    if hidden_gate is not None and scope != getattr(
        executor, "HIDDEN_SCOPE", "hidden-ok"
    ):
        hidden_gate(scope)
    fams = list(families) if families else suite_families(suite, executor)
    run_id = run_id or make_run_id("RUN-{}".format(suite.replace("-", "")))
    try:
        from progress import NullProgress, ProgressReporter
    except ImportError:
        from shared.progress import NullProgress
    prog = progress if progress is not None else NullProgress()
    total = 0
    for _family in fams:
        try:
            n_variants = len(_family_variants(executor, _family))
        except Exception:
            n_variants = 1
        total += max(instances, 1) * n_variants * max(trials, 1)
    prog.start_suite(suite, total_attempts=total)
    prog.add_suite_total(total)
    attempts, responses = [], []
    # Streaming writer (roadmap Phase 3): lines hit disk per attempt;
    # the bundle is still published atomically at the end. Aborted on
    # round-level failure (scope denial etc.): no partial RUN dir.
    out_root = out_root or os.path.join(ROOT, "results", "raw")
    stream = BundleStream(out_root, run_id)
    try:
        _run_suite_loop(
            executor,
            suite,
            chat,
            model_id,
            backend,
            seed,
            instances,
            trials,
            fault_rate,
            fams,
            run_id,
            provider_profile,
            scope,
            sampling,
            prog,
            attempts,
            responses,
            stream,
            force=force,
        )
    except BaseException:
        stream.abort()
        raise
    conditions = sorted({a.get("reasoning_mode", "unknown") for a in attempts})
    manifest = build_manifest(
        suite,
        executor.prompt_pack_sha256(),
        executor.harness_sha256(),
        model_id,
        backend,
        seed,
        max(trials, 1),
        run_id,
        provider_profile=provider_profile,
        sampling=sampling,
        model_modalities=model_modalities,
        model_type=model_type,
        extra={
            "claim_tier": SUITE_CLAIM_TIER.get(suite, DEFAULT_CLAIM_TIER),
            "reasoning_conditions": conditions,
        },
    )
    rundir = stream.close(manifest, collect_environment())
    n_pass = sum(1 for a in attempts if a["primary_status"] == "PASS")
    prog.finish_suite()
    summary = {
        "run_id": run_id,
        "suite": suite,
        "n_attempts": len(attempts),
        "n_pass": n_pass,
        "run_dir": rundir,
        "prompt_sha256": manifest["prompt_sha256"],
        "harness_sha256": manifest["harness_sha256"],
    }
    return rundir, summary


def run_profile(
    chat,
    model_id="stub-model",
    backend="stub",
    seed=0,
    instances=1,
    trials=1,
    fault_rate=0.25,
    out_root=None,
    provider_profile=None,
    scope=None,
    sampling=None,
    progress=None,
    model_modalities=None,
    model_type=None,
):
    """SPEC 42 --suite profile: every suite once + v2 roll-up report."""
    try:
        from report_v2 import build_v2_report
    except ImportError:
        from shared.report_v2 import build_v2_report
    try:
        from progress import NullProgress
    except ImportError:
        from shared.progress import NullProgress
    prog = progress if progress is not None else NullProgress()
    prog.start_run(total_suites=len(PROFILE_SUITES))
    runs, all_attempts, all_responses = [], [], []
    for idx, suite in enumerate(PROFILE_SUITES, 1):
        prog.set_suite_index(idx)
        _, summary = run_suite(
            suite,
            chat,
            model_id,
            backend,
            seed,
            instances,
            trials,
            fault_rate,
            out_root,
            provider_profile=provider_profile,
            scope=scope,
            sampling=sampling,
            progress=prog,
            model_modalities=model_modalities,
            model_type=model_type,
        )
        runs.append(summary)
    for summary in runs:
        rundir = summary["run_dir"]
        with open(os.path.join(rundir, "events.jsonl"), encoding="utf-8") as f:
            all_attempts.extend(json.loads(line) for line in f if line.strip())
        with open(os.path.join(rundir, "responses.jsonl"), encoding="utf-8") as f:
            all_responses.extend(json.loads(line) for line in f if line.strip())
    report = build_v2_report(all_attempts, all_responses, model_id=model_id)
    prog.finish_run()
    return runs, report


# ---------------------------------------------------------------------------
# SPEC 35: harness self-test (fail-closed, delegated to shared/selftest.py)
# ---------------------------------------------------------------------------


def run_self_test():
    """Fail-closed harness verification. SPEC 35.

    Delegated to shared/selftest.py (Y-2, 14 checks + SKIP semantics).
    Returns (ok_bool, rows). ok is True iff every check passes; callers
    must refuse benchmark execution otherwise (fail closed).
    """
    try:
        from selftest import run_all_checks
    except ImportError:  # pragma: no cover - path fallback (X-2 pattern)
        from shared.selftest import run_all_checks
    return run_all_checks()


# ---------------------------------------------------------------------------
# --health: benchmark-health snapshot over raw runs
# ---------------------------------------------------------------------------


def health_snapshot(out_root=None):
    """Assemble benchmark-health signals from stored raw runs + rules."""
    import health.contamination as _con
    import health.discrimination as _dsc
    import health.flakiness as _flk
    import health.saturation as _sat

    flakiness_snapshot = _flk.flakiness_snapshot
    validity_snapshot = _flk.validity_snapshot
    saturation_snapshot = _sat.saturation_snapshot
    discrimination_snapshot = _dsc.discrimination_snapshot
    build_model_task_matrix = _dsc.build_model_task_matrix
    contamination_snapshot = _con.contamination_snapshot
    out_root = out_root or os.path.join(ROOT, "results", "raw")
    attempts = []
    if os.path.isdir(out_root):
        for run_id in sorted(os.listdir(out_root)):
            path = os.path.join(out_root, run_id, "events.jsonl")
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        attempts.append(json.loads(line))
    by_task_status = {}
    for a in attempts:
        by_task_status.setdefault(a.get("task_family_id"), []).append(
            a.get("primary_status")
        )
    n_error = sum(1 for a in attempts if a.get("primary_status") == "ERROR")
    tasks = {}
    for task, statuses in by_task_status.items():
        tasks[task] = {"flakiness": flakiness_snapshot(statuses)}
    matrix = build_model_task_matrix(attempts) if attempts else {}
    disc = (
        {t: discrimination_snapshot(matrix, t) for t in by_task_status}
        if matrix
        else {}
    )
    # Contamination pairs (P2-14): per-family (canonical, novel) pass
    # rates over scored attempts; novel = novel/adversarial/hidden
    # variants. Retention collapse flags the TASK for rotation.
    pairs_by_task = {}
    for task in by_task_status:
        canon_all = [
            a
            for a in attempts
            if a.get("task_family_id") == task
            and a.get("primary_status") in ("PASS", "FAIL")
            and (a.get("variant_class") or "canonical") == "canonical"
        ]
        canon = [a for a in canon_all if a.get("primary_status") == "PASS"]
        novel = [
            a
            for a in attempts
            if a.get("task_family_id") == task
            and a.get("primary_status") in ("PASS", "FAIL")
            and (a.get("variant_class") or "") in ("novel", "adversarial", "hidden")
        ]
        novel_pass = sum(1 for a in novel if a.get("primary_status") == "PASS")
        if canon_all and novel:
            pairs_by_task[task] = (len(canon) / len(canon_all), novel_pass / len(novel))
    pairs = list(pairs_by_task.values())
    # Saturation per task (P2-15): reference scores across models.
    saturation = {}
    for task in by_task_status:
        ref = [scores.get(task) for scores in matrix.values()] if matrix else []
        saturation[task] = saturation_snapshot(ref)
    saturated_tasks = sorted(t for t, s in saturation.items() if s.get("saturated"))
    contaminated_tasks = sorted(
        t
        for t, p in pairs_by_task.items()
        if contamination_snapshot(pairs=[p]).get("level") == "high"
    )
    return {
        "n_attempts": len(attempts),
        "n_models": len(matrix),
        "validity": validity_snapshot(n_error, len(attempts)),
        "tasks": tasks,
        "discrimination": disc,
        "contamination": contamination_snapshot(pairs=pairs),
        "contamination_by_task": {
            t: contamination_snapshot(pairs=[p]) for t, p in pairs_by_task.items()
        },
        "saturation": saturation,
        "saturated_tasks": saturated_tasks,
        "rotation_candidates": sorted(set(saturated_tasks) | set(contaminated_tasks)),
    }
