"""Variant transforms: canonical -> perturbed/structural/novel family.

Contract refs: SPEC section 6 (NEVER embed expected answers in
generated prompts), SPEC section 9 (generalization matrix levels
C/P/S/A/R/N) and SPEC section 10 (difficulty ladder D0-D7).

Every transform is a *pure* function ``instance -> instance``:
the input dict is never mutated, the oracle is recomputed from the
(new) parameters via ``generators/instance_factory.py`` so it stays
recomputable, both hashes are refreshed, and the output carries
exactly one primary variant (variant-exclusivity, DEN C14).

SPEC section 9 level map used here:
* C canonical      — baseline capability
* P paraphrase     — robustness (rewording only)
* S naming/constraint/structural — reasoning/generalization
* A adversarial    — benign misleading context (SPEC 23), not an attack
* R recovery       — controlled failure injected (SPEC 13)
* N novel          — contamination-resistant resampling
"""

from copy import deepcopy

try:
    from schemas import SchemaError
except ImportError:  # package-style import (repo root on sys.path)
    from shared.schemas import SchemaError
try:
    from task_dsl import VALID_VARIANTS
except ImportError:  # package-style import (repo root on sys.path)
    from generators.task_dsl import VALID_VARIANTS
try:
    from seeds import (make_rng, derive_child_seed, make_instance_id,
                       parse_instance_id, canonical_hash,
                       build_instance_record)
except ImportError:  # package-style import (repo root on sys.path)
    from generators.seeds import (make_rng, derive_child_seed,
                                  make_instance_id, parse_instance_id,
                                  canonical_hash, build_instance_record)
try:
    from instance_factory import (resolve_parameters, compute_oracle,
                                  render_prompt, prompt_leaks_oracle)
except ImportError:  # package-style import (repo root on sys.path)
    from generators.instance_factory import (resolve_parameters,
                                             compute_oracle, render_prompt,
                                             prompt_leaks_oracle)

#: The mutually-exclusive primary variant labels (DEN C14).
PRIMARY_VARIANTS = tuple(VALID_VARIANTS)

#: SPEC section 9 generalization level per primary variant.
VARIANT_LEVELS = {
    "canonical": "C",
    "paraphrase": "P",
    "naming": "S",
    "constraint": "S",
    "structural": "S",
    "adversarial": "A",
    "recovery": "R",
    "novel": "N",
}

#: Suggested SPEC section 10 difficulty bump per variant kind.
VARIANT_DIFFICULTY_BUMP = {
    "canonical": 0,
    "paraphrase": 0,
    "naming": 1,
    "constraint": 1,
    "structural": 2,
    "adversarial": 2,
    "recovery": 3,
    "novel": 2,
}

_PARAPHRASE_FRAMES = (
    "Restated: {body} Answer with the final value only.",
    "In other words, {body} Give just the final value.",
)

_ADVERSARIAL_NOTE = (
    " Note: an archived comment nearby claims a different method applies, "
    "but follow the problem statement as written and verify your own work.")

_RECOVERY_CONTEXT = (
    "The first tool attempt failed with TOOL_TIMEOUT (transient). "
    "Diagnose, retry with an alternative strategy, then verify.")


class VariantError(ValueError):
    """Raised when variant exclusivity or transform preconditions break."""


def primary_variant(instance):
    """Return the instance's exactly-one primary variant. DEN C14.

    Raises VariantError when the instance carries zero, several, or an
    unknown primary variant label.
    """
    if not isinstance(instance, dict):
        raise VariantError("instance must be a dict")
    variant = instance.get("variant")
    if isinstance(variant, list) or variant not in PRIMARY_VARIANTS:
        raise VariantError("instance must carry exactly one primary "
                           "variant, got %r" % (variant,))
    if "variants" in instance:
        raise VariantError("instance must not carry a plural 'variants' "
                           "label set (variant-exclusivity, DEN C14)")
    return variant


def variant_level(variant):
    """Return the SPEC section 9 level (C/P/S/A/R/N) for a variant."""
    if variant not in VARIANT_LEVELS:
        raise VariantError("unknown variant: %r" % (variant,))
    return VARIANT_LEVELS[variant]


def _check_base(instance):
    """Validate a transform input. Returns a deep copy. SPEC 9."""
    if not isinstance(instance, dict):
        raise VariantError("instance must be a dict")
    for key in ("instance_id", "task", "seed", "generator_version",
                "parameters", "prompt", "oracle"):
        if key not in instance:
            raise VariantError("instance missing %r" % key)
    primary_variant(instance)  # input must already be exclusive
    return deepcopy(instance)


def _finalize(base, variant, parameters, prompt, task_name=None):
    """Recompute oracle + hashes for a transformed instance. SPEC 6/8.

    The oracle is always freshly derived from ``parameters`` (never
    copied blindly, never rendered into the prompt).
    """
    family, _, index = parse_instance_id(base["instance_id"])
    name = task_name or base.get("task_name", base["task"])
    oracle = compute_oracle(base["task"], name, parameters)
    if prompt_leaks_oracle(prompt, oracle):
        raise VariantError("transform leaked the expected answer "
                           "into the prompt (SPEC 6)")
    record = build_instance_record(base["task"], base["seed"],
                                   base["generator_version"], parameters,
                                   oracle, variant=variant)
    out = dict(base)
    out.update({
        "instance_id": make_instance_id(family, variant, index),
        "variant": variant,
        "parameters": parameters,
        "prompt": prompt,
        "oracle": oracle,
        "instance_hash": record["instance_hash"],
        "oracle_hash": record["oracle_hash"],
        "derived_from": base["instance_id"],
        "generalization_level": VARIANT_LEVELS[variant],
    })
    return out


def apply_paraphrase(instance):
    """P-level rewording: same parameters, restated prompt. SPEC 9."""
    base = _check_base(instance)
    body = base["prompt"]
    rng = make_rng(base["seed"], base["generator_version"])
    frame = _PARAPHRASE_FRAMES[rng.randrange(len(_PARAPHRASE_FRAMES))]
    return _finalize(base, "paraphrase", base["parameters"],
                     frame.format(body=body))


def apply_naming(instance):
    """S-level identifier renaming in the prompt. SPEC 9.

    Swaps surface identifiers deterministically (no semantic change,
    parameters and oracle untouched).
    """
    base = _check_base(instance)
    prompt = base["prompt"]
    swaps = (("remainder", "residue"), ("divided by", "modulo"),
             ("final", "resulting"))
    rng = make_rng(derive_child_seed(base["seed"],
                                     base["generator_version"], "naming"),
                   base["generator_version"])
    order = sorted(swaps, key=lambda _s: rng.random())
    for old, new in order[:2]:
        prompt = prompt.replace(old, new)
    prompt = "Renamed restatement: " + prompt
    return _finalize(base, "naming", base["parameters"], prompt)


def apply_constraint(instance):
    """S-level constraint mutation: extra output constraint. SPEC 9."""
    base = _check_base(instance)
    parameters = dict(base["parameters"])
    parameters["output_constraint"] = "single_integer_no_explanation"
    prompt = (base["prompt"]
              + " Constraint: output a single integer only, "
                "no words and no explanation.")
    return _finalize(base, "constraint", parameters, prompt)


def apply_structural(instance, parameters_spec=None):
    """S-level structural change: resampled numeric parameters. SPEC 9.

    Re-derives parameters from the manifest-style ``parameters_spec``
    when given, else deterministically perturbs numeric parameters with
    a seed-derived stream. The oracle is recomputed either way.
    """
    base = _check_base(instance)
    if parameters_spec is not None:
        rng = make_rng(derive_child_seed(
            base["seed"], base["generator_version"], "structural"),
            base["generator_version"])
        parameters = resolve_parameters(parameters_spec, rng)
        manifest_stub = {"id": base["task"],
                         "name": base.get("task_name", base["task"])}
        prompt = render_prompt(manifest_stub, parameters)
    else:
        rng = make_rng(derive_child_seed(
            base["seed"], base["generator_version"], "structural"),
            base["generator_version"])
        parameters = dict(base["parameters"])
        for key in sorted(parameters):
            value = parameters[key]
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                parameters[key] = value + rng.randint(1, 9)
            elif isinstance(value, float):
                parameters[key] = value + rng.uniform(0.5, 2.0)
        prompt = ("Structural variant of %s with parameters: %s. "
                  "Return only the final answer with no explanation."
                  % (base["instance_id"], ", ".join(
                      "%s=%s" % (k, parameters[k])
                      for k in sorted(parameters))))
    return _finalize(base, "structural", parameters, prompt)


def apply_adversarial(instance):
    """A-level benign misleading context (SPEC 9, SPEC 23).

    Appends a stale-comment style distractor to the prompt. It never
    changes the parameters or the oracle, and never states an answer.
    """
    base = _check_base(instance)
    prompt = base["prompt"] + _ADVERSARIAL_NOTE
    return _finalize(base, "adversarial", base["parameters"], prompt)


def apply_recovery(instance):
    """R-level controlled failure injection (SPEC 9, SPEC 13).

    Records a transient TOOL_TIMEOUT the agent must recover from.
    The underlying task parameters and oracle are unchanged.
    """
    base = _check_base(instance)
    parameters = dict(base["parameters"])
    parameters["injected_fault"] = "TOOL_TIMEOUT"
    prompt = base["prompt"] + " " + _RECOVERY_CONTEXT
    out = _finalize(base, "recovery", parameters, prompt)
    out["recoverable"] = True
    return out


def apply_novel(instance, parameters_spec):
    """N-level contamination-resistant resampling. SPEC 9.

    Draws fresh parameters from ``parameters_spec`` with a derived
    child seed so the novel instance differs from the canonical one
    while remaining fully reproducible.
    """
    base = _check_base(instance)
    if not isinstance(parameters_spec, dict) or not parameters_spec:
        raise VariantError("parameters_spec must be a non-empty mapping")
    rng = make_rng(derive_child_seed(base["seed"],
                                     base["generator_version"], "novel"),
                   base["generator_version"])
    parameters = resolve_parameters(parameters_spec, rng)
    manifest_stub = {"id": base["task"],
                     "name": base.get("task_name", base["task"])}
    prompt = render_prompt(manifest_stub, parameters)
    return _finalize(base, "novel", parameters, prompt)


#: Registry of all variant transforms (canonical excluded). SPEC 9.
TRANSFORMS = {
    "paraphrase": apply_paraphrase,
    "naming": apply_naming,
    "constraint": apply_constraint,
    "structural": apply_structural,
    "adversarial": apply_adversarial,
    "recovery": apply_recovery,
    "novel": apply_novel,
}


def apply_variant(instance, variant, **kwargs):
    """Apply one named variant transform. SPEC 9."""
    if variant == "canonical":
        raise VariantError("canonical is the base instance, not a transform")
    try:
        func = TRANSFORMS[variant]
    except KeyError:
        raise VariantError("unknown variant: %r" % (variant,))
    return func(instance, **kwargs)
