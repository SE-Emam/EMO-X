# Metrics

Contract refs: SPEC Part B (B1-B63, normative formulas), DEN Part C
(C1-C93, denominators), SPEC 29 (capability profile, never one number).

## Rules

- NA is `None`; `D=0` implies `None`, never 0 (DEN C90-C91).
- Missing eligibility flags default to eligible `True`.
- Aggregation order: Attempt -> Instance -> Variant -> Task ->
  Capability (DEN C78, SPEC B6). Equal variant weights renormalize over
  observed variants only (C17); unobserved families are UNOBSERVED (C11).
- `ERROR`/`VOID` never enter a model-performance denominator (DEN C9);
  they lower Coverage (B3, threshold 0.95 for official runs).
- Every metric resolves its denominator through
  `shared/denominators.py::METRIC_REGISTRY` (C81) via
  `eligible_attempts()` — never reinvented.
- B12/C47 resolution: generalization default is the arithmetic mean
  (C47 amendment applies); harmonic form is the auxiliary
  "Generalization-H".

## Capability profile (SPEC B60-B61)

Public result = capability profile + failure fingerprint + efficiency +
uncertainty (95% cluster-bootstrap CI over task families, B54/C65) +
coverage + health. `EMO_Overall` exists only for eligible runs;
otherwise the run is NOT RANKABLE (gate B56: CSVRate=0, Coverage>=0.95,
Health>=0.80, >=90% required-dimension weight per C75).

## Scorecard (SPEC 44)

Recommended public fields: correctness, generalization, tool
discipline, recovery, robustness, safety, calibration, efficiency, long
horizon, human-equivalent minutes, tokens/solved task, tool calls per
success, recovery rate, clean-stop rate, failure fingerprint bands.

## Novelty Robustness (official variable)

`scoring.novelty_robustness(C, P, N)`: harmonic mean over the
canonical / perturbed / novel levels. A memorizing model (C=1.0,
N=0.2) scores <0.5; a robust one (0.96/0.92/0.94) scores >0.9. Any NA
level propagates NA (C90). Report the C/P/N triple beside it — the
triple answers "skill or memory?", not the 24/25.

## Human Time Horizon Lite (SPEC 26)

Every task manifest carries `estimated_human_minutes`; the runner
attaches it to responses (`runner.manifest_minutes`), and
`report_v2` reports human-minutes solved/strict/rate. Same 22/25 can
mean 91 or 138 human-minutes — the minutes measure work, the ratio
measures correctness.

## Judge audit (Tier 5 guardrail)

`judges/judge_audit.py`: perturb judge inputs (order swap, verbosity
pad, tail truncation, conflicting restatement, dual language) and
measure flip rates. `stability` < 0.90 marks the judge UNSTABLE —
mirroring the B52 reliability gate, with special attention to
cross-language degradation.

## Model comparison calls (B54, no fixed point-gap rule)

`report_v2.compare_models(attempts_a, attempts_b, model_a, model_b,
manifest_a, manifest_b, B, seed)` reports pass rate plus 95%
cluster-bootstrap CI per model and the paired A-B difference with its
interval. Comparability via
`manifests.comparability_with_capabilities` gates the call: a
`NON_COMPARABLE` verdict yields status `non-comparable` with no duel
numbers, only the reason. Otherwise the status is:

- `significant` — the paired 95% CI excludes zero.
- `directional` — the CI covers zero but at least 90% of bootstrap
  replicates share the point-estimate sign (a lean, not a verdict).
- `inconclusive` — default for the rest; do not rank on the gap.
  A 24/25 vs 23/25 split lands here (or `directional`), never
  `significant`.
- `insufficient-data` — no paired task families to resample.

`report_v2.render_comparison` prints the per-model rates, the
`Difference` line with its interval, and the `Status` line, using
ranking-free language throughout.
