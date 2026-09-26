"""Canonical instance factory for EMO-X suites (stdlib only).

Shared convention (converged with X-2 generators, no waiting):
  instance_id = f"{family}-{variant}-{index:05d}"
e.g. "H3-canonical-00001". The seed is recorded in every instance record.
Hashes use shared/manifests.py sha256_manifest (canonical sorted-key JSON).

Raw records only: no scoring here (X-3 owns scoring).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

from manifests import sha256_bytes, sha256_manifest  # noqa: E402

CANONICAL_VARIANT = "canonical"


def make_instance_id(family, variant=CANONICAL_VARIANT, index=1):
    """Build the canonical instance id for a family/variant/index."""
    return "%s-%s-%05d" % (family, variant, index)


def make_instance(family, prompt_text, manifest,
                  variant=CANONICAL_VARIANT, index=1, seed=0):
    """Build a canonical instance record with recorded seed + hashes."""
    instance_id = make_instance_id(family, variant, index)
    return {
        "task_family_id": family,
        "instance_id": instance_id,
        "variant_class": variant,
        "index": index,
        "seed": seed,
        "prompt_sha256": sha256_bytes(prompt_text.encode("utf-8")),
        "manifest_sha256": sha256_manifest(manifest),
    }
