"""Task DSL manifest loader, validator, and SHA256 hashing (stdlib only).

Contract refs: SPEC section 7 (Task DSL), SPEC section 32 (run manifest),
comparison-validity rule B58 (PromptHash+HarnessHash+ManifestHash).
"""

import hashlib
import json
import os

try:
    from schemas import validate_task_manifest, SchemaError
except ImportError:  # `python shared/x.py` vs package import
    from shared.schemas import validate_task_manifest, SchemaError


def load_task_manifest(source):
    """Load a task manifest from a dict, JSON string, or file path. SPEC 7.

    Returns the validated manifest dict. Raises SchemaError on failure.
    """
    if isinstance(source, dict):
        data = source
    elif isinstance(source, str):
        if os.path.exists(source):
            with open(source, encoding="utf-8") as f:
                text = f.read()
        else:
            text = source
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise SchemaError("task manifest is not valid JSON: %s" % e)
    else:
        raise SchemaError("unsupported manifest source type")
    return validate_task_manifest(data)


def sha256_bytes(data):
    """Return hex SHA256 of bytes. SPEC 32."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    """Return hex SHA256 of a file's bytes. SPEC 32."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_manifest(manifest):
    """Return canonical SHA256 of a manifest dict (B58 ManifestHash).

    Uses sorted-key canonical JSON so equal manifests hash equally.
    """
    canonical = json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def comparison_key(prompt_sha256, harness_sha256, manifest_sha256):
    """Build the B58 comparison-validity key. SPEC B58.

    Two runs are DIRECT-comparable only when all three hashes match.
    """
    return {
        "prompt_sha256": prompt_sha256,
        "harness_sha256": harness_sha256,
        "manifest_sha256": manifest_sha256,
    }


def is_directly_comparable(key_a, key_b):
    """True iff two B58 comparison keys match exactly. SPEC B58."""
    return (
        key_a.get("prompt_sha256") == key_b.get("prompt_sha256")
        and key_a.get("harness_sha256") == key_b.get("harness_sha256")
        and key_a.get("manifest_sha256") == key_b.get("manifest_sha256")
    )


def comparability_with_capabilities(key_a, key_b, cap_a, cap_b):
    """Full comparison verdict: hashes first, capabilities second.

    SPEC B58 + SPEC 36. Hash mismatch always wins (NON_COMPARABLE —
    different code/prompts cannot be saved by equal backends). Otherwise
    defers to backends.comparability() without importing it (cap dicts
    compared structurally: DIRECT iff all material fields equal and known).
    """
    if not is_directly_comparable(key_a, key_b):
        return ("NON_COMPARABLE", "B58 hash mismatch")
    material = (
        "tool_calls",
        "reasoning_tokens",
        "seed",
        "token_usage",
        "vision",
        "stop_behavior",
        "max_tokens",
    )
    for field in material:
        a, b = (cap_a or {}).get(field), (cap_b or {}).get(field)
        if a == b:
            continue
        if "unknown" in (a, b):
            return ("CONDITIONALLY_COMPARABLE", "unverified capability %r" % field)
        return ("NON_COMPARABLE", "material conflict in %r: %r vs %r" % (field, a, b))
    if any((cap_a or {}).get(f) == "unknown" for f in material):
        return ("CONDITIONALLY_COMPARABLE", "unverified material capability")
    return ("DIRECT", "identical material capabilities")


def verify_prompt_pack(pack_name, root=None):
    """Verify a frozen prompt pack against prompts/SHA256SUMS. SPEC B59.

    Returns True iff the pack file hash matches its SHA256SUMS entry.
    Raises VoidRun("prompt-changed...") on tamper, missing entry, or
    missing file (prompt-tamper => VOID per DEN C6). root overrides the
    repo root for testability.
    """
    try:
        from schemas import VoidRun
    except ImportError:  # `python shared/x.py` vs package import
        from shared.schemas import VoidRun
    base = (
        os.path.normpath(root)
        if root is not None
        else os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    )
    name = str(pack_name)
    if name.endswith(".md"):
        name = name[:-3]
    if name == "PROMPT_PACK_v1":
        rel = os.path.join("shared", "PROMPT_PACK_v1.md")
    elif name == "PROMPT_PACK_v2":
        rel = os.path.join("prompts", "PROMPT_PACK_v2.md")
    else:
        raise VoidRun("prompt-changed: unknown pack %r" % (pack_name,))
    sums_path = os.path.join(base, "prompts", "SHA256SUMS")
    pack_path = os.path.join(base, rel)
    try:
        with open(sums_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        raise VoidRun("prompt-changed: cannot read SHA256SUMS")
    expected = None
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 2 and os.path.basename(parts[1]) == name + ".md":
            expected = parts[0]
            break
    if expected is None:
        raise VoidRun("prompt-changed: no SHA256SUMS entry for %r" % (name,))
    try:
        actual = sha256_file(pack_path)
    except OSError:
        raise VoidRun("prompt-changed: missing pack file %r" % (rel,))
    if actual != expected:
        raise VoidRun("prompt-changed: hash mismatch for %s" % name)
    return True
