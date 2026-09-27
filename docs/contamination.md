# Contamination Policy (SPEC 38)

Public/hidden evaluation separation for EMO-X.

## 1. Two tiers

| Tier | Suites | Purpose | Claim language |
|---|---|---|---|
| Public / dev | `code-bench-25`, `dynamic-code`, all visible suites | Development, debugging, iteration | `PUBLIC-BENCHMARK` |
| Maintainer / hidden | `code-bench-25-hidden` (HH1–HH6, runtime-generated, canary-tagged) | Final validation only | `HIDDEN-VALIDATION` |

Rules:

- Public instances and prompts may be inspected, logged, and trained on
  at the developer's own risk. Scores on public suites alone never
  support a generalization claim.
- Hidden instances are generated at runtime from generator CONFIG plus
  seeds. They are never written to the repo, never logged with answers,
  and never published. A hidden score supports a `HIDDEN-VALIDATION`
  claim only when the run manifest records the hidden prompt-pack hash,
  the executor harness hash, and the opt-in scope.
- Any result that mixes public and hidden evidence must label each
  number with its tier. Unlabeled numbers default to
  `PUBLIC-BENCHMARK`.

## 2. Seed custody

- Hidden seeds live with the maintainer (CI secret or local-only file
  outside the repo). They are passed at runtime via `--seed` /
  environment and are never committed.
- The repo stores only generator CONFIG (parameter ranges in
  `suites/code-bench-25-hidden/manifests/*.json`) plus the oracle
  descriptor. CONFIG is public; seeds and instances are not.
- Test and example seeds (e.g. `seed=25000` in unit tests) are
  synthetic smoke seeds. They exercise the generator path but carry no
  validation weight and must never be presented as hidden results.
- If a hidden seed is ever published, quoted in an issue, or lands in
  a log artifact, treat it as burned: rotate immediately per section 3.

## 3. Rotation rule

- Rotate hidden seeds on a fixed schedule (at least once per release)
  and immediately after any suspected exposure.
- Rotation means: pick fresh seeds, re-run the hidden validation set,
  record the new run manifest, and retire the old seeds. The generator
  CONFIG stays stable so rotation changes instances without changing
  the prompt-pack hash.
- If the generator CONFIG itself changes (new ranges, new oracle),
  bump the suite version and re-baseline: old `HIDDEN-VALIDATION`
  numbers are historical, not comparable.

## 4. Claim language

- `PUBLIC-BENCHMARK`: "Model M scores S on public suite P (seed s,
  harness h)." Development-grade evidence.
- `HIDDEN-VALIDATION`: "Model M scores S on hidden suite H
  (prompt-pack p, harness h, seed custody maintained, scope hidden-ok)."
  Validation-grade evidence.
- Never present a `PUBLIC-BENCHMARK` number as validation. Never
  publish hidden instances, prompts with answers, or seeds to justify
  a claim; publish the run manifest hashes instead.
