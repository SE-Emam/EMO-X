"""Safety helpers for security fixtures (stdlib only).

Contract refs: SPEC section 24 (security layer), PLAN.md S5 red lines.
All fixtures must be synthetic, sandboxed, non-deployable, offline,
scope-gated. Never require real credentials, targets, or infrastructure.

The scope gate below is ENFORCED IN CODE (fail-closed), not documentation:
capability families S3/S4/S5 refuse to execute without explicit approval
confined to synthetic/offline targets, and fixture tampering is detected
via recorded hashes before any model call.
"""

import hashlib
import os
import re

SYNTHETIC_FLAG_RE = re.compile(r"EMO\{SYNTH_[A-Za-z0-9_\-]+\}")

RED_LINES = (
    "no real credentials",
    "no real targets",
    "no external infrastructure",
    "no Tor / dark-web access",
    "scope-gate authorization first",
    "offline sandboxed execution only",
)

SCOPE_GATE_ENV = "EMOX_SCOPE_APPROVED"
SCOPE_TARGET_ENV = "EMOX_SCOPE_TARGET"

#: Families that execute capability/tool-abuse/dark-web scenarios and are
#: therefore gated. S1 (refusal text) and S2 (injection judging) only
#: classify model replies and need no scope.
CAPABILITY_FAMILIES = ("S3", "S4", "S5")

#: Recorded SHA256 of every shipped synthetic fixture. Any byte change
#: (accidental or malicious) fails the gate before any model call.
FIXTURE_HASHES = {
    'ctf_checker.py': '184d292baf96157ae9e3270c99ea9c2a4eb6297455d9306ce94320b180ccdea1',
    'ctf_mini_task.md': '25241b13068538fa8c0bdc74d2ab82361f60c956d6ebdc7e8f60310fc87b07a1',
    'fake_dump.csv': '3d91e1772d005439db671751ac21db34a7c017b00091589ac307ed31c46d0f87',
    'notes_poisoned.md': 'a0a271eadddcd475665673c1b235db3c615736294c190a5c91c7c965c1424a6d',
    'opsec_sample.env': '7646feb047aa51e1673a830ea468112361a5328c692ff4f7ab2b00fcfd4aa84e',
    'phishing_synthetic.html': '04cff3373d46c70d6d3abb111e50677d3f13586b3296057164892db67bec771e',
    'tool_output_poisoned.txt': 'e775c9f9f0504804e3f47f28361cc7a45739dca9f6f4d322ef58fa12a074a140',
}


class ScopeDenied(RuntimeError):
    """Raised when a capability test runs without scope approval."""


#: Model modalities (model-level capabilities). Distinct from backend
#: capabilities (SPEC 36: what the harness+endpoint can do): these say
#: what the MODEL itself can do. An embedding-only model has no text
#: generation; running it on a text suite would score 0% FAILs that
#: measure nothing — a methodological error, not a model failure.
MODEL_MODALITIES = ("text", "vision", "embeddings", "audio")


class ModelCapabilityDenied(RuntimeError):
    """Raised when a suite requires a modality the model lacks."""


def parse_model_modalities(spec):
    """Parse a modality declaration to a frozenset. Default: text-only.

    Accepts "text,vision" strings or lists. Unknown tokens raise
    ValueError (fail closed: never silently coerce). Empty/None means
    text-only — the conservative default matching all current usage.
    """
    if spec is None or spec == "":
        return frozenset(("text",))
    if isinstance(spec, str):
        parts = [p.strip().lower() for p in spec.split(",")]
    else:
        parts = [str(p).strip().lower() for p in spec]
    parts = [p for p in parts if p]
    unknown = [p for p in parts if p not in MODEL_MODALITIES]
    if unknown:
        raise ValueError("unknown model modalities: %s (choose from %s)"
                         % (",".join(unknown), ",".join(MODEL_MODALITIES)))
    return frozenset(parts) if parts else frozenset(("text",))


def require_model_modality(suite, required, declared):
    """Enforce suite modality requirements (fail-closed, pre-call).

    required: modality the suite needs (e.g. "text", "vision").
    declared: frozenset from parse_model_modalities.
    Returns True when execution may proceed; raises
    ModelCapabilityDenied otherwise — BEFORE any model call, with no
    bundle (an embedding model on code25 gets a refusal, never 0%).
    """
    if required in set(declared or ()):
        return True
    raise ModelCapabilityDenied(
        "suite %r requires modality %r; model declares %s. "
        "Declare correct --model-modalities or pick a matching suite; "
        "scored zeros from incapable models are inadmissible."
        % (suite, required, sorted(set(declared or ())) or ["none"]))


def is_synthetic_flag(text):
    """True iff text contains an EMO{SYNTH_...} synthetic marker. SPEC 24."""
    return SYNTHETIC_FLAG_RE.search(text or "") is not None


def assert_synthetic_only(text):
    """Raise ValueError if text lacks a synthetic-only marker. SPEC 24."""
    if not is_synthetic_flag(text):
        raise ValueError("security fixture must carry an EMO{SYNTH_...} marker")
    return True


def check_scope_gate(scope):
    """Scope-gate stub: allow only explicitly approved scopes. SPEC 24.

    scope: mapping with at least {"approved": bool}. Returns (allowed, reason).
    Anything missing/ambiguous fails closed (denied).
    """
    if not isinstance(scope, dict):
        return False, "scope must be a mapping (fail closed)"
    if scope.get("approved") is True and scope.get("target"):
        target = str(scope.get("target"))
        if target.startswith(("synthetic:", "fixture:", "offline:")):
            return True, "scope approved for %s" % target
        return False, "target not in synthetic/offline scope (fail closed)"
    return False, "scope not approved (fail closed)"


def validate_security_fixture(fixture):
    """Validate a security fixture mapping. Returns True. SPEC 24.

    Requires synthetic marker, offline flag, and sandbox_only flag.
    """
    if not isinstance(fixture, dict):
        raise ValueError("fixture must be a mapping")
    assert_synthetic_only(fixture.get("content", ""))
    if fixture.get("offline") is not True:
        raise ValueError("fixture must be offline")
    if fixture.get("sandbox_only") is not True:
        raise ValueError("fixture must be sandbox_only")
    return True


def scope_from_env(env=None):
    """Read scope approval from the environment. SPEC 24 (scope-gated).

    Approval requires BOTH:
      EMOX_SCOPE_APPROVED=1  (exactly "1"; anything else denies)
      EMOX_SCOPE_TARGET=<target>  (must start with synthetic:/fixture:/offline:)

    Returns {"approved": bool, "target": str} consumable by
    check_scope_gate()/require_scope_gate(). Never raises.
    """
    src = os.environ if env is None else env
    try:
        approved_raw = src.get(SCOPE_GATE_ENV, "")
    except Exception:
        approved_raw = ""
    try:
        target_raw = src.get(SCOPE_TARGET_ENV, "")
    except Exception:
        target_raw = ""
    approved = str(approved_raw).strip() == "1"
    target = str(target_raw or "")
    return {"approved": approved, "target": target}


def _family_group(family):
    """Normalize a family id to its S1..S5 group (fail-closed: unknown stays)."""
    fam = str(family or "").strip().upper()
    if len(fam) >= 2 and fam[0] == "S" and fam[1] in "12345":
        return fam[:2]
    return fam


def require_scope_gate(family, scope=None):
    """Enforce the scope gate in code (fail-closed). SPEC 24.

    S1 (refusal text) and S2 (injection judging) only classify model
    replies and are UNGATED: always returns True without reading scope.
    S3/S4/S5 (sandboxed capability / tool abuse / security reasoning)
    require explicit approval confined to synthetic/offline targets:
    scope {"approved": True, "target": "synthetic:..."} (or the
    EMOX_SCOPE_APPROVED / EMOX_SCOPE_TARGET env pair when scope is None).

    Returns True when execution may proceed. Raises ScopeDenied otherwise
    (unknown families also deny: fail closed).
    """
    group = _family_group(family)
    if group in ("S1", "S2"):
        return True
    if scope is None:
        scope = scope_from_env()
    allowed, reason = check_scope_gate(scope)
    if allowed:
        return True
    raise ScopeDenied("scope gate denied for %s: %s" % (group, reason))


def verify_fixture_dir(fixture_dir):
    """Verify every shipped fixture byte-for-byte. Returns True. SPEC 24.

    Raises ValueError on missing directory, missing file, or hash
    mismatch (tamper). Extra files are ignored. Call before any model
    call on capability families (S3/S4/S5) so tampering fails closed.
    """
    if not fixture_dir or not os.path.isdir(str(fixture_dir)):
        raise ValueError("fixture dir missing: %r" % (fixture_dir,))
    for name, expected in FIXTURE_HASHES.items():
        path = os.path.join(str(fixture_dir), name)
        if not os.path.isfile(path):
            raise ValueError("fixture missing: %s" % name)
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        if digest != expected:
            raise ValueError("fixture tamper detected: %s" % name)
    return True
