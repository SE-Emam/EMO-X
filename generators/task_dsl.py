"""Task DSL dataclass/dict model + validation.

Contract refs: SPEC section 6 (task family model — a task must never
encode the expected answer into the prompt generator) and SPEC section 7
(Task DSL manifest fields).

Validation is layered on the manifest schema in ``shared/schemas.py``:
first the shared contract (required top-level fields), then deeper
per-section checks defined here. Stdlib only.
"""

from dataclasses import dataclass, field

try:
    from schemas import validate_task_manifest, SchemaError
except ImportError:  # package-style import (repo root on sys.path)
    from shared.schemas import validate_task_manifest, SchemaError
try:
    from manifests import sha256_manifest
except ImportError:  # package-style import (repo root on sys.path)
    from shared.manifests import sha256_manifest

# SPEC section 7: generator kinds.
VALID_GENERATOR_TYPES = ("parametric", "template", "static")

# SPEC section 9 generalization levels C/P/S/A/R/N, plus the SPEC section 5
# H3 family spellings (naming/constraint are structural-level mutations).
VALID_VARIANTS = (
    "canonical",
    "paraphrase",
    "naming",
    "constraint",
    "structural",
    "adversarial",
    "recovery",
    "novel",
)

# SPEC section 10: adaptive difficulty ladder D0-D7.
DIFFICULTY_LABELS = (
    "trivial",
    "standard",
    "perturbed",
    "constrained",
    "adversarial",
    "recovery",
    "compound",
    "long-horizon",
)
MIN_DIFFICULTY = 0
MAX_DIFFICULTY = 7

# SPEC P6 judging hierarchy mapped to oracle.type spellings.
VALID_ORACLE_TYPES = ("deterministic", "execution", "ast_diff", "trajectory_rule", "llm_judge")


def example_h3_manifest():
    """Return the SPEC section 7 H3 example manifest as a dict."""
    return {
        "id": "H3",
        "version": "1.0",
        "name": "modular_arithmetic",
        "category": "reasoning",
        "capabilities": ["mathematical_reasoning", "verification", "generalization"],
        "generator": {
            "type": "parametric",
            "seed": "random",
            "parameters": {
                "modulus": {"min": 11, "max": 997},
                "coefficient": {"distribution": "uniform", "min": 2, "max": 10},
                "target": {"distribution": "uniform", "min": 10, "max": 200},
            },
        },
        "difficulty": {"base": 3, "adaptive": True},
        "execution": {"type": "python"},
        "oracle": {"type": "deterministic"},
        "scoring": {"correctness": 1.0, "explanation": 0.25, "verification": 0.25},
        "variants": ["canonical", "paraphrase", "structural", "adversarial", "recovery"],
        "timeouts": {"generation_seconds": 120, "execution_seconds": 30},
        "network": {"allowed": False},
        "filesystem": {"sandbox_only": True},
    }


def validate_task_dict(record):
    """Validate a Task DSL manifest dict. SPEC section 7.

    Runs ``shared/schemas.py::validate_task_manifest`` first, then
    deep-checks each section. Returns a normalized (copied) dict.
    Raises SchemaError on any violation.
    """
    base = validate_task_manifest(record)  # required fields + section types
    out = dict(base)

    for key in ("id", "version", "name", "category"):
        val = out[key]
        if not isinstance(val, str) or not val:
            raise SchemaError("%s must be a non-empty string" % key)

    if not all(isinstance(c, str) and c for c in out["capabilities"]):
        raise SchemaError("capabilities must be a list of non-empty strings")
    if not all(isinstance(v, str) and v for v in out["variants"]):
        raise SchemaError("variants must be a list of non-empty strings")
    unknown = [v for v in out["variants"] if v not in VALID_VARIANTS]
    if unknown:
        raise SchemaError("unknown variants: %r" % (unknown,))

    gen = out["generator"]
    if "type" not in gen or gen["type"] not in VALID_GENERATOR_TYPES:
        raise SchemaError("generator.type must be one of %r" % (VALID_GENERATOR_TYPES,))
    if "parameters" in gen and not isinstance(gen["parameters"], dict):
        raise SchemaError("generator.parameters must be a mapping")

    diff = out["difficulty"]
    if "base" not in diff:
        raise SchemaError("difficulty.base is required")
    base_level = diff["base"]
    if (
        isinstance(base_level, bool)
        or not isinstance(base_level, int)
        or not (MIN_DIFFICULTY <= base_level <= MAX_DIFFICULTY)
    ):
        raise SchemaError(
            "difficulty.base must be an int in D%d-D%d" % (MIN_DIFFICULTY, MAX_DIFFICULTY)
        )
    if "adaptive" in diff and not isinstance(diff["adaptive"], bool):
        raise SchemaError("difficulty.adaptive must be bool")

    if (
        "type" not in out["execution"]
        or not isinstance(out["execution"]["type"], str)
        or not out["execution"]["type"]
    ):
        raise SchemaError("execution.type must be a non-empty string")

    if "type" not in out["oracle"] or out["oracle"]["type"] not in VALID_ORACLE_TYPES:
        raise SchemaError("oracle.type must be one of %r" % (VALID_ORACLE_TYPES,))

    for weight_name, weight in out["scoring"].items():
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
            raise SchemaError("scoring.%s must be a non-negative number" % weight_name)

    for timeout_name, timeout in out["timeouts"].items():
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout < 0:
            raise SchemaError("timeouts.%s must be a non-negative number" % timeout_name)

    return out


def manifest_hash(record):
    """Return the B58 ManifestHash of a task manifest. SPEC B58.

    Uses ``shared/manifests.py::sha256_manifest`` (canonical sorted-key
    JSON) so every agent hashes identically.
    """
    return sha256_manifest(validate_task_dict(record))


def difficulty_label(base):
    """Return the SPEC section 10 label for difficulty level D{base}."""
    if not MIN_DIFFICULTY <= base <= MAX_DIFFICULTY:
        raise SchemaError("difficulty out of range D%d-D%d" % (MIN_DIFFICULTY, MAX_DIFFICULTY))
    return DIFFICULTY_LABELS[base]


@dataclass
class TaskDSL:
    """Typed Task DSL model. SPEC section 7.

    Instances are always created via :meth:`from_dict` so the shared
    contract plus deep checks apply. Use :meth:`to_dict` for canonical
    JSON / hashing round-trips.
    """

    id: str
    version: str
    name: str
    category: str
    capabilities: list = field(default_factory=list)
    generator: dict = field(default_factory=dict)
    difficulty: dict = field(default_factory=dict)
    execution: dict = field(default_factory=dict)
    oracle: dict = field(default_factory=dict)
    scoring: dict = field(default_factory=dict)
    variants: list = field(default_factory=list)
    timeouts: dict = field(default_factory=dict)
    network: dict = field(default_factory=dict)
    filesystem: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, record):
        """Build a TaskDSL from a manifest dict (validated). SPEC 7."""
        data = validate_task_dict(record)
        return cls(
            **{
                f: data[f]
                for f in (
                    "id",
                    "version",
                    "name",
                    "category",
                    "capabilities",
                    "generator",
                    "difficulty",
                    "execution",
                    "oracle",
                    "scoring",
                    "variants",
                    "timeouts",
                    "network",
                    "filesystem",
                )
            }
        )

    @classmethod
    def from_json(cls, text):
        """Build a TaskDSL from a JSON string (validated). SPEC 7."""
        import json

        try:
            data = json.loads(text)
        except ValueError as exc:
            raise SchemaError("task manifest is not valid JSON: %s" % exc)
        return cls.from_dict(data)

    def to_dict(self):
        """Return the manifest as a plain (validated) dict. SPEC 7."""
        return validate_task_dict(
            {
                "id": self.id,
                "version": self.version,
                "name": self.name,
                "category": self.category,
                "capabilities": self.capabilities,
                "generator": self.generator,
                "difficulty": self.difficulty,
                "execution": self.execution,
                "oracle": self.oracle,
                "scoring": self.scoring,
                "variants": self.variants,
                "timeouts": self.timeouts,
                "network": self.network,
                "filesystem": self.filesystem,
            }
        )

    def hash(self):
        """Return this task's B58 ManifestHash. SPEC B58."""
        return manifest_hash(self.to_dict())
