"""EMO-X generators package (X-2, WP4).

Deterministic Task DSL + instance generation per SPEC sections 6-10.
Canonical hashing always goes through
``shared/manifests.py::sha256_manifest`` (B58 ManifestHash).
"""

from generators.task_dsl import TaskDSL, validate_task_dict  # noqa: F401
from generators.seeds import (GENERATOR_VERSION, make_rng,  # noqa: F401
                              make_instance_id, parse_instance_id,
                              build_instance_record, canonical_hash)
from generators.instance_factory import (build_instance,  # noqa: F401
                                         verify_oracle, compute_oracle,
                                         prompt_leaks_oracle)
from generators.mutations import (apply_variant, primary_variant,  # noqa: F401
                                  variant_level, TRANSFORMS,
                                  PRIMARY_VARIANTS, VARIANT_LEVELS)
