"""Build canonical task instances from a task manifest.

Contract refs: SPEC section 6 (task family model — NEVER embed expected
answers in generated prompts), SPEC section 7 (Task DSL) and SPEC
section 8 (seed -> generator -> instance -> oracle -> execution).

Determinism contract: ``build_instance`` with the same manifest + seed +
variant + index yields a byte-identical ``instance_hash`` on any
machine. Only ``random.Random`` (string-seeded), sorted-key iteration
and canonical JSON are used on the hashed path — no timestamps, no
``hash()``, no UUIDs, no set iteration.

Stdlib only.
"""

from copy import deepcopy
import re

try:
    from schemas import SchemaError
except ImportError:  # package-style import (repo root on sys.path)
    from shared.schemas import SchemaError
try:
    from manifests import sha256_manifest
except ImportError:  # package-style import (repo root on sys.path)
    from shared.manifests import sha256_manifest
try:
    from task_dsl import validate_task_dict, TaskDSL
except ImportError:  # package-style import (repo root on sys.path)
    from generators.task_dsl import validate_task_dict, TaskDSL
try:
    from seeds import (GENERATOR_VERSION, make_rng, make_instance_id,
                       build_instance_record, canonical_hash)
except ImportError:  # package-style import (repo root on sys.path)
    from generators.seeds import (GENERATOR_VERSION, make_rng,
                                  make_instance_id, build_instance_record,
                                  canonical_hash)


#: H3 dynamic-equation axes (SPEC 9: same oracle kind, varied surface).
#: perturbed = new numbers/names, same representation class.
#: novel = new representation (remainder/code form) + irrelevant context.
H3_VAR_NAMES = ("x", "n", "k", "t")
H3_FORMS = ("congruence", "remainder", "code")
H3_WORDINGS = (
    "Solve for {v}: {a}{v} ≡ {b} (mod {m}). "
    "Reply with ONLY the final integer 0 ≤ {v} < {m}, no explanation.",
    "Find the integer {v} with 0 ≤ {v} < {m} satisfying "
    "{a}·{v} ≡ {b} (mod {m}). Reply with ONLY the final integer.",
)
H3_REMAINDER_WORDINGS = (
    "When {a}·{v} is divided by {m}, the remainder is {b}. "
    "Find the smallest non-negative {v}. Reply with ONLY the final integer.",
    "The remainder of {a}·{v} upon division by {m} equals {b}. "
    "Give the smallest {v} ≥ 0. Reply with ONLY the final integer.",
)
H3_CODE_WORDINGS = (
    "Complete: {v} = ___ such that ({a} * {v}) % {m} == {b} "
    "with 0 ≤ {v} < {m}. Reply with ONLY the final integer.",
    "A program asserts ({a} * {v}) % {m} == {b} for 0 ≤ {v} < {m}. "
    "Find {v}. Reply with ONLY the final integer.",
)
#: Irrelevant context pool (novel only). Numbers here are noise by design;
#: the checker therefore anchors on the trailing answer, never bare ints.
H3_CONTEXTS = (
    "A warehouse tracks 42 crates across 7 aisles; this is unrelated. ",
    "Bus route 12 departs every 15 minutes; this is unrelated. ",
    "A library holds 300 books on 9 shelves; this is unrelated. ",
)
H3_NOVEL_FRAME = "In other words, {body} State the final value only."

#: H3 math subtypes (SPEC 9, P0-08). The frozen canonical H3 prompt
#: (shared/PROMPT_PACK_v1.md) is modular EXPONENTIATION (remainder of
#: 3^100 divided by 7), so generated perturbed/novel instances offer an
#: "exp" subtype (new base/exponent/modulus c^t mod m) alongside the
#: legacy "linear" subtype (unique solution of a*v == b mod m).
H3_SUBTYPES = ("linear", "exp")
#: H3 exponentiation axes (SPEC 9: same oracle kind as the canonical
#: prompt — a single remainder — with varied surface). perturbed = new
#: numbers, standard power wording. novel = new representation
#: (remainder/code form) + irrelevant context.
H3_EXP_FORMS = ("power", "remainder", "code")
H3_EXP_WORDINGS = (
    "What is the remainder when {c}^{t} is divided by {m}? "
    "Be concise and state the final remainder clearly.",
    "Find the remainder of {c}^{t} upon division by {m}. "
    "Reply with ONLY the final integer.",
)
H3_EXP_REMAINDER_WORDINGS = (
    "When {c}^{t} is divided by {m}, what is the remainder? "
    "Reply with ONLY the final integer.",
    "The remainder of {c}^{t} upon division by {m} equals what? "
    "Give ONLY the final integer.",
)
H3_EXP_CODE_WORDINGS = (
    "Complete: result = ({c} ** {t}) % {m} with result == ___ "
    "and 0 <= result < {m}. Reply with ONLY the final integer.",
    "A program asserts ({c} ** {t}) % {m} == ___ for the missing value "
    "with 0 <= result < {m}. Find the value. "
    "Reply with ONLY the final integer.",
)


def _h3_gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def build_h3_equation(seed, variant="perturbed", index=1,
                      generator_version=GENERATOR_VERSION,
                      subtype="linear"):
    """H3.seed -> parametric modular-equation instance. SPEC 9.

    Same mathematical oracle kind as canonical H3 with varied surface:
    numbers, variable names, representation (congruence/remainder/code),
    wording, and (novel only) irrelevant context. The expected answer is
    NEVER rendered into the prompt (SPEC 6).

    variant: "perturbed" (new numbers/names, standard wording) or
      "novel" (new representation + context + reframe).
    subtype: "linear" (default, legacy unique solution of a·v ≡ b mod
      m — byte-identical to the pre-P0-08 generator) or "exp"
      (modular exponentiation c^t mod m — the oracle kind of the
      frozen canonical prompt, SPEC B/C remainder oracle).
    Returns the build_instance() record shape.
    """
    if variant not in ("perturbed", "novel"):
        raise SchemaError("H3 dynamic variant must be perturbed|novel")
    if subtype not in H3_SUBTYPES:
        raise SchemaError("H3 math subtype must be linear|exp")
    if subtype == "exp":
        return _build_h3_exp_equation(seed, variant, index,
                                      generator_version)
    rng = make_rng(seed * 100003 + index, generator_version)
    modulus = rng.randint(11, 99)
    coefficient = 1
    for _ in range(200):  # deterministic rejection: unique-solution only
        candidate = rng.randint(2, modulus + 20)
        if _h3_gcd(candidate, modulus) == 1:
            coefficient = candidate
            break
    else:  # pragma: no cover - unreachable (density of units is high)
        raise SchemaError("cannot draw coprime coefficient")
    target = rng.randint(1, 199)
    var = H3_VAR_NAMES[rng.randrange(len(H3_VAR_NAMES))]
    if variant == "perturbed":
        form = "congruence"
        body = H3_WORDINGS[rng.randrange(len(H3_WORDINGS))].format(
            v=var, a=coefficient, b=target, m=modulus)
        prompt = body
    else:
        form = H3_FORMS[rng.randrange(len(H3_FORMS))]
        if form == "congruence":
            body = H3_WORDINGS[rng.randrange(len(H3_WORDINGS))]
        elif form == "remainder":
            body = H3_REMAINDER_WORDINGS[
                rng.randrange(len(H3_REMAINDER_WORDINGS))]
        else:
            body = H3_CODE_WORDINGS[rng.randrange(len(H3_CODE_WORDINGS))]
        body = body.format(v=var, a=coefficient, b=target, m=modulus)
        prompt = (H3_CONTEXTS[rng.randrange(len(H3_CONTEXTS))]
                  + H3_NOVEL_FRAME.format(body=body))
    expected = (pow(coefficient, -1, modulus) * target) % modulus
    parameters = {"coefficient": coefficient, "target": target,
                  "modulus": modulus, "variable": var, "form": form}
    oracle = {"oracle_type": "deterministic", "task": "H3",
              "equation": "%d*v=%d mod %d (unique, gcd=1)"
                          % (coefficient, target, modulus),
              "expected": expected}
    record = build_instance_record("H3", seed, generator_version,
                                   parameters, oracle, variant=variant)
    return {
        "instance_id": make_instance_id("H3", variant, index),
        "task": record["task"],
        "task_name": "modular_equation",
        "variant": variant,
        "seed": record["seed"],
        "generator_version": record["generator_version"],
        "parameters": parameters,
        "prompt": prompt,
        "oracle": oracle,
        "instance_hash": record["instance_hash"],
        "oracle_hash": record["oracle_hash"],
    }


def _build_h3_exp_equation(seed, variant, index, generator_version):
    """H3.seed -> modular-exponentiation instance. SPEC 9.

    Oracle kind matches the frozen canonical H3 prompt
    (shared/PROMPT_PACK_v1.md: remainder of c^t divided by m):
    perturbed draws a new base/exponent/modulus with standard power
    wording; novel rewords (remainder/code form) and prepends
    irrelevant context. The expected remainder is NEVER rendered into
    the prompt (SPEC 6). Deterministic: same seed + index yields a
    byte-identical instance_hash on any machine (SPEC 8).
    """
    rng = make_rng(seed * 100003 + index, generator_version)
    modulus = rng.randint(5, 50)
    base = rng.randint(2, 20)
    exponent = rng.randint(10, 150)
    if variant == "perturbed":
        form = "power"
        prompt = H3_EXP_WORDINGS[
            rng.randrange(len(H3_EXP_WORDINGS))].format(
                c=base, t=exponent, m=modulus)
    else:
        form = H3_EXP_FORMS[rng.randrange(len(H3_EXP_FORMS))]
        if form == "power":
            body = H3_EXP_WORDINGS[rng.randrange(len(H3_EXP_WORDINGS))]
        elif form == "remainder":
            body = H3_EXP_REMAINDER_WORDINGS[
                rng.randrange(len(H3_EXP_REMAINDER_WORDINGS))]
        else:
            body = H3_EXP_CODE_WORDINGS[
                rng.randrange(len(H3_EXP_CODE_WORDINGS))]
        body = body.format(c=base, t=exponent, m=modulus)
        prompt = (H3_CONTEXTS[rng.randrange(len(H3_CONTEXTS))]
                  + H3_NOVEL_FRAME.format(body=body))
    expected = pow(base, exponent, modulus)
    parameters = {"base": base, "exponent": exponent,
                  "modulus": modulus, "form": form}
    oracle = {"oracle_type": "deterministic", "task": "H3",
              "equation": "pow(%d,%d) mod %d (remainder)"
                          % (base, exponent, modulus),
              "expected": expected}
    record = build_instance_record("H3", seed, generator_version,
                                   parameters, oracle, variant=variant)
    return {
        "instance_id": make_instance_id("H3", variant, index),
        "task": record["task"],
        "task_name": "modular_exponentiation",
        "variant": variant,
        "seed": record["seed"],
        "generator_version": record["generator_version"],
        "parameters": parameters,
        "prompt": prompt,
        "oracle": oracle,
        "instance_hash": record["instance_hash"],
        "oracle_hash": record["oracle_hash"],
    }


def check_h3_equation(reply, expected, subtype="linear"):
    """Verify an H3-equation reply against the oracle solution.

    Anchored on the trailing `= N` answer (novel prompts contain noise
    numbers by design); falls back to the last bare integer for clean
    perturbed prompts. Returns (ok_bool, detail). SPEC 9.

    subtype: "linear" (a·v ≡ b mod m solution) or "exp" (c^t mod m
    remainder) — both expect a single trailing integer, so the check
    logic is shared; the parameter is validated and selects the
    detail tag for auditability.
    """
    if subtype not in H3_SUBTYPES:
        raise SchemaError("H3 math subtype must be linear|exp")
    tag = "equation-check" if subtype == "linear" else "modexp-check"
    text = reply or ""
    anchored = re.findall(r"=\s*(-?\d+)", text)
    if anchored:
        return bool(int(anchored[-1]) == expected), tag
    bare = re.findall(r"-?\d+", text)
    if bare:
        return bool(int(bare[-1]) == expected), tag
    return False, tag + ":no-integer"



def resolve_value(spec, rng):
    """Resolve one parameter spec to a concrete value. SPEC 8.

    Supported spec forms (anything else is returned as-is, i.e. const):
    * ``{"min": int, "max": int}`` -> ``rng.randint(min, max)``
    * ``{"min": float, "max": float}`` -> ``rng.uniform(min, max)``
    * ``{"distribution": "uniform", "min": a, "max": b}`` -> int or
      float draw depending on the bound types
    * ``{"choices": [...]}`` -> ``rng.choice(choices)``
    * ``{"const": v}`` / ``{"value": v}`` -> ``v``
    * nested plain mappings are resolved recursively (sorted keys).
    """
    if isinstance(spec, dict):
        if "choices" in spec:
            choices = spec["choices"]
            if not isinstance(choices, list) or not choices:
                raise SchemaError("choices must be a non-empty list")
            return deepcopy(choices[rng.randrange(len(choices))])
        if "const" in spec:
            return deepcopy(spec["const"])
        if "value" in spec and set(spec) == {"value"}:
            return deepcopy(spec["value"])
        if "min" in spec and "max" in spec:
            lo, hi = spec["min"], spec["max"]
            dist = spec.get("distribution", "uniform")
            if dist != "uniform":
                raise SchemaError("unsupported distribution: %r" % (dist,))
            if (isinstance(lo, bool) or isinstance(hi, bool)
                    or not isinstance(lo, (int, float))
                    or not isinstance(hi, (int, float)) or lo > hi):
                raise SchemaError("bad range spec: %r" % (spec,))
            if isinstance(lo, int) and isinstance(hi, int):
                return rng.randint(lo, hi)
            return rng.uniform(lo, hi)
        if "distribution" in spec:
            raise SchemaError("distribution needs min/max: %r" % (spec,))
        return {key: resolve_value(spec[key], rng) for key in sorted(spec)}
    if isinstance(spec, list):
        return deepcopy(spec)
    return deepcopy(spec)


def resolve_parameters(parameters_spec, rng):
    """Resolve a generator.parameters mapping. SPEC 8.

    Keys are visited in sorted order so resolution order (and hence RNG
    draw order) is identical on every machine.
    """
    if not isinstance(parameters_spec, dict):
        raise SchemaError("generator.parameters must be a mapping")
    if rng is None or not hasattr(rng, "randint"):
        raise SchemaError("rng must be a random.Random stream")
    return {key: resolve_value(parameters_spec[key], rng)
            for key in sorted(parameters_spec)}


def compute_oracle(task_id, task_name, parameters):
    """Derive the oracle payload from concrete parameters. SPEC 6/8.

    The oracle is always *recomputed* from parameters — it is stored
    alongside the instance for the harness, never rendered into the
    prompt (SPEC 6). Families with a registered closed form get an
    ``expected`` value; all other families get a ``params_digest``
    payload that is still fully recomputable via :func:`verify_oracle`.
    """
    params = deepcopy(parameters)
    if task_name == "modular_arithmetic" and all(
            k in params for k in ("modulus", "coefficient", "target")):
        modulus = int(params["modulus"])
        coefficient = int(params["coefficient"])
        target = int(params["target"])
        if modulus <= 0:
            raise SchemaError("modulus must be positive")
        return {"oracle_type": "deterministic",
                "task": task_id,
                "expected": pow(coefficient, target, modulus)}
    return {"oracle_type": "deterministic",
            "task": task_id,
            "params_digest": canonical_hash(params)}


def render_prompt(manifest, parameters):
    """Render the canonical prompt for concrete parameters. SPEC 6.

    Contains parameter values (the question) but NEVER the oracle's
    expected answer — enforced by the no-answer-leak tests.
    """
    name = manifest["name"]
    task_id = manifest["id"]
    if name == "modular_arithmetic":
        return (
            "What is the remainder when %s^%s is divided by %s? "
            "Be concise and state the final remainder clearly."
            % (parameters["coefficient"], parameters["target"],
               parameters["modulus"]))
    ordered = ", ".join("%s=%s" % (key, parameters[key])
                        for key in sorted(parameters))
    return ("Solve task '%s' (%s) with parameters: %s. "
            "Return only the final answer with no explanation."
            % (name, task_id, ordered))


def prompt_leaks_oracle(prompt, oracle):
    """True if the prompt text contains the oracle's expected answer.

    SPEC 6 guard used by the test-suite (and available to X-4/X-5).
    Only the registered ``expected`` payload is checked; digest-style
    oracles carry no answer by construction.
    """
    expected = oracle.get("expected")
    if expected is None:
        return False
    return str(expected) in prompt


def build_instance(manifest, seed, variant="canonical", index=1,
                   generator_version=GENERATOR_VERSION):
    """Build one canonical instance from a task manifest. SPEC 7/8.

    ``manifest`` is a Task DSL dict (or :class:`TaskDSL`); ``seed`` an
    int; ``variant`` must be ``"canonical"`` here (use
    ``generators/mutations.py`` for the other primary variants);
    ``index`` feeds the MANDATORY ``instance_id`` convention shared
    with X-4.

    Returns ``{instance_id, task, variant, seed, generator_version,
    parameters, prompt, oracle, instance_hash, oracle_hash}``.
    """
    if isinstance(manifest, TaskDSL):
        manifest = manifest.to_dict()
    manifest = validate_task_dict(manifest)
    if not isinstance(variant, str) or not variant:
        raise SchemaError("variant must be a non-empty string")
    if variant != "canonical":
        raise SchemaError("factory builds canonical instances only; "
                          "use generators/mutations.py for %r" % (variant,))

    task_id = manifest["id"]
    rng = make_rng(seed, generator_version)
    parameters = resolve_parameters(
        manifest["generator"].get("parameters", {}), rng)
    oracle = compute_oracle(task_id, manifest["name"], parameters)
    prompt = render_prompt(manifest, parameters)
    record = build_instance_record(task_id, seed, generator_version,
                                   parameters, oracle, variant=variant)
    return {
        "instance_id": make_instance_id(task_id, variant, index),
        "task": record["task"],
        "task_name": manifest["name"],
        "variant": variant,
        "seed": record["seed"],
        "generator_version": record["generator_version"],
        "parameters": parameters,
        "prompt": prompt,
        "oracle": oracle,
        "instance_hash": record["instance_hash"],
        "oracle_hash": record["oracle_hash"],
    }


def verify_oracle(instance, manifest_or_name=None):
    """Recompute the oracle from instance parameters. SPEC 6/8.

    Returns True iff the stored oracle equals a fresh recomputation —
    i.e. the oracle survived a variant transform intact. Accepts the
    instance's stored task name when no manifest is supplied.
    """
    if not isinstance(instance, dict):
        raise SchemaError("instance must be a dict")
    for key in ("task", "parameters", "oracle"):
        if key not in instance:
            raise SchemaError("instance missing %r" % key)
    if manifest_or_name is None:
        name = instance.get("task_name", instance["task"])
        fresh = compute_oracle(instance["task"], name,
                               instance["parameters"])
    elif isinstance(manifest_or_name, dict):
        manifest = validate_task_dict(manifest_or_name)
        fresh = compute_oracle(manifest["id"], manifest["name"],
                               instance["parameters"])
    else:
        fresh = compute_oracle(instance["task"], manifest_or_name,
                               instance["parameters"])
    return (fresh == instance["oracle"]
            and canonical_hash(fresh) == instance["oracle_hash"])
