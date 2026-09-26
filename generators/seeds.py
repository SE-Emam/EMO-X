"""Deterministic seed handling for instance generation.

Contract refs: SPEC section 8 (dynamic instance generation — the seed
must be recorded so another researcher can recreate the exact test).

Rules implemented here:
* ``seed`` (int) + ``generator_version`` (str) -> one reproducible
  ``random.Random`` stream, seeded with ``f"{generator_version}:{seed}"``.
* ``instance_id`` convention (MANDATORY, shared with X-4 suites):
  ``f"{family}-{variant}-{index:05d}"``, e.g. ``"H3-canonical-00001"``.
* Instance record ``{task, seed, generator_version, instance_hash,
  oracle_hash}`` per SPEC section 8, where both hashes use the
  ``shared/manifests.py::sha256_manifest`` canonical sorted-key JSON —
  the B58 ManifestHash every agent uses.

Stdlib only. No timestamps, no ``hash()``, no set iteration anywhere on
the hashed path, so equal inputs hash equally on any machine.
"""

import random
import re

try:
    from schemas import SchemaError
except ImportError:  # package-style import (repo root on sys.path)
    from shared.schemas import SchemaError
try:
    from manifests import sha256_manifest
except ImportError:  # package-style import (repo root on sys.path)
    from shared.manifests import sha256_manifest

#: Version of the instance-generation scheme itself. Bumped whenever the
#: parameter-resolution or oracle-derivation semantics change (SPEC 45:
#: a change of task semantics/oracle = new version + re-baseline).
GENERATOR_VERSION = "1.0.0"

_SEED_STREAM_FORMAT = "{version}:{seed}"


def check_seed(seed):
    """Validate a seed value. SPEC 8. Returns the seed unchanged."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise SchemaError("seed must be an int, got %r" % (seed,))
    return seed


def check_generator_version(version):
    """Validate a generator version string. SPEC 8."""
    if not isinstance(version, str) or not version:
        raise SchemaError("generator_version must be a non-empty string")
    return version


def stream_tag(seed, generator_version):
    """Return the RNG stream tag ``"{version}:{seed}"``. SPEC 8."""
    check_seed(seed)
    check_generator_version(generator_version)
    return _SEED_STREAM_FORMAT.format(version=generator_version, seed=seed)


def make_rng(seed, generator_version=GENERATOR_VERSION):
    """Return a reproducible ``random.Random`` stream. SPEC 8.

    The stream is seeded with ``f"{generator_version}:{seed}"`` so the
    same pair always yields the same draws on any machine (stdlib
    ``random.Random`` with a string seed is platform-stable), while a
    generator-version bump intentionally re-baselines every stream.
    """
    return random.Random(stream_tag(seed, generator_version))


def derive_child_seed(seed, generator_version, salt, index=0):
    """Derive a deterministic child seed (int) from a parent seed. SPEC 8.

    Used by novel resampling and structural mutations: pure function of
    its inputs, stable across machines (sha256-based, never ``hash()``).
    """
    check_seed(seed)
    check_generator_version(generator_version)
    if not isinstance(salt, str) or not salt:
        raise SchemaError("salt must be a non-empty string")
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise SchemaError("index must be a non-negative int")
    digest = sha256_manifest({
        "generator_version": generator_version,
        "index": index,
        "salt": salt,
        "seed": seed,
    })
    return int(digest[:16], 16)


def make_instance_id(family, variant, index):
    """Build an instance id ``"{family}-{variant}-{index:05d}"``. SPEC 8.

    This convention is MANDATORY and shared with X-4 (suites): every
    generated instance id must round-trip through :func:`parse_instance_id`.
    """
    if not isinstance(family, str) or not family:
        raise SchemaError("family must be a non-empty string")
    if not isinstance(variant, str) or not variant:
        raise SchemaError("variant must be a non-empty string")
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise SchemaError("index must be a non-negative int")
    if "-" in variant:
        raise SchemaError("variant must not contain '-': %r" % (variant,))
    return "%s-%s-%05d" % (family, variant, index)


def parse_instance_id(instance_id):
    """Split an instance id into ``(family, variant, index)``. SPEC 8.

    Raises SchemaError when the id does not follow the MANDATORY
    ``"{family}-{variant}-{index:05d}"`` convention.
    """
    if not isinstance(instance_id, str):
        raise SchemaError("instance_id must be a string")
    parts = instance_id.rsplit("-", 2)
    if len(parts) != 3:
        raise SchemaError("bad instance_id: %r" % (instance_id,))
    family, variant, index_text = parts
    if (not family or not variant
            or not re.fullmatch(r"\d{5}", index_text or "")):
        raise SchemaError("bad instance_id: %r" % (instance_id,))
    return family, variant, int(index_text)


def canonical_hash(payload):
    """Hash any JSON-able payload with the B58 canonical hash. SPEC B58.

    Thin alias over ``shared/manifests.py::sha256_manifest`` kept here so
    generator code has a single obvious hashing entry point.
    """
    return sha256_manifest(payload)


def build_instance_record(task, seed, generator_version, parameters,
                          oracle, variant="canonical"):
    """Build the SPEC section 8 instance record.

    Returns ``{task, seed, generator_version, instance_hash,
    oracle_hash}`` where ``instance_hash`` covers the canonical
    ``{task, variant, parameters, seed, generator_version}`` payload and
    ``oracle_hash`` covers the canonical oracle payload.
    """
    if not isinstance(task, str) or not task:
        raise SchemaError("task must be a non-empty string")
    if not isinstance(variant, str) or not variant:
        raise SchemaError("variant must be a non-empty string")
    if not isinstance(parameters, dict):
        raise SchemaError("parameters must be a mapping")
    if not isinstance(oracle, dict):
        raise SchemaError("oracle must be a mapping")
    check_seed(seed)
    check_generator_version(generator_version)
    return {
        "task": task,
        "seed": seed,
        "generator_version": generator_version,
        "instance_hash": canonical_hash({
            "generator_version": generator_version,
            "parameters": parameters,
            "seed": seed,
            "task": task,
            "variant": variant,
        }),
        "oracle_hash": canonical_hash(oracle),
    }
