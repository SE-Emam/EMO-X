# PROMPT_PACK v2 — Dynamic-Generation Prompts (EMO-X)

> Version `v2` — 2026-09-25. Generator scheme `1.0.0` (`generators/`).
> This pack renders prompts for *generated* instances (EMO-Core-Dynamic,
> SPEC sections 7-9). `PROMPT_PACK_v1` stays frozen for the canonical
> Core-25 baseline; a run must cite exactly one pack (SPEC B58:
> DIRECT comparison only on equal PromptHash+HarnessHash+ManifestHash).
> Sampling defaults: user message only, `temp=0.4`, no system prompt for
> code/reasoning families (agent-loop families keep their suite SYSTEM).

## Rendering contract (SPEC section 6)

1. The renderer receives `{task, parameters, variant}` and fills the
   placeholders below. It MUST NEVER interpolate the oracle's `expected`
   value or any paraphrase of it into the prompt.
2. Parameter values are the question, not the answer: rendering
   `modulus=997` is required; rendering the remainder is forbidden.
3. Adversarial/recovery variants add *context* (stale notes, transient
   failures) but never hints toward the answer.
4. Every rendered prompt is checked with
   `generators/instance_factory.py::prompt_leaks_oracle` before release.

## V2.1 Canonical (level C — baseline capability)

`What is the remainder when {coefficient}^{target} is divided by
{modulus}? Be concise and state the final remainder clearly.`

Generic families without a dedicated template use:

`Solve task '{name}' ({id}) with parameters: {k1=v1, k2=v2, ...}.
Return only the final answer with no explanation.`

## V2.2 Paraphrase (level P — robustness)

Same parameters as canonical. One of:

- `Restated: {canonical_prompt} Answer with the final value only.`
- `In other words, {canonical_prompt} Give just the final value.`

Choice is RNG-derived from `seed + generator_version` (reproducible).

## V2.3 Naming (level S — surface generalization)

Canonical prompt with identifiers swapped (`remainder`->`residue`,
`divided by`->`modulo`, `final`->`resulting`), prefixed with
`Renamed restatement: `. Parameters and oracle unchanged.

## V2.4 Constraint (level S — constrained output)

Canonical prompt plus: ` Constraint: output a single integer only, no
words and no explanation.` Records
`parameters.output_constraint=single_integer_no_explanation`.

## V2.5 Structural (level S — reasoning/generalization)

Parameters are re-derived (perturbed numerics or a fresh draw from the
manifest's `generator.parameters`); the oracle is recomputed. Prompt:

`Structural variant of {parent_instance_id} with parameters:
{k1=v1, ...}. Return only the final answer with no explanation.`

## V2.6 Adversarial (level A — benign noise, SPEC 23)

Canonical prompt plus: ` Note: an archived comment nearby claims a
different method applies, but follow the problem statement as written
and verify your own work.` Parameters and oracle unchanged. The note is
deliberately answer-free; it tests evidence-following, not security.

## V2.7 Recovery (level R — controlled failure, SPEC 13)

Canonical prompt plus: `The first tool attempt failed with TOOL_TIMEOUT
(transient). Diagnose, retry with an alternative strategy, then
verify.` Records `parameters.injected_fault=TOOL_TIMEOUT` and
`recoverable=true`. The underlying task is unchanged.

## V2.8 Novel (level N — contamination resistance)

Fresh parameters drawn from `generator.parameters` with the derived
child seed (`novel` salt); rendered with the generic/canonical template
for the family. Nothing is copied from any previously seen instance.

## V2.9 Difficulty mapping (SPEC 10)

Base difficulty comes from the manifest (`difficulty.base`, D0-D7).
Variant bumps (advisory for the adaptive controller in
`shared/adaptive.py`): canonical +0, paraphrase +0, naming +1,
constraint +1, structural +2, adversarial +2, recovery +3, novel +2.

## Hash note

This file's SHA256 is recorded in `prompts/SHA256SUMS` next to the
frozen v1 hash. Any edit — even whitespace — invalidates existing
baselines run under v2 and requires a re-baseline (SPEC 45).
