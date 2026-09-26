# EMO-X architecture

Contract refs: SPEC sections 3 (architecture), 4 (layers), 41 (repository),
33 (immutable results).

## Pipeline

```text
Task Factory (seed + generator DSL, SPEC 7-8)
  -> Adaptive Difficulty Controller D0-D7 (SPEC 10, shared/adaptive.py)
  -> Evaluation Harness + Prompt Pack (SPEC P2; packs frozen, B58)
  -> Model / Agent (tool interaction or direct output)
  -> Execution Sandbox (shared/sandbox.py, SPEC 24/35)
  -> Correctness / Trajectory / Safety judges (judges/, SPEC P6)
  -> Scoring + Metrics (shared/scoring.py, SPEC Part B; denominators
     from shared/denominators.py, DEN Part C)
  -> Failure Fingerprint (judges/trajectory.py, SPEC 30)
  -> Benchmark Health (health/, SPEC 11-12)
  -> Report / Profile (shared/report_v2.py, SPEC 43-44)
```

## Capability layers (SPEC 4)

L0 Core Execution, L1 Generalization, L2 Tool Use, L3 Recovery,
L4 Robustness, L5 Security, L6 Calibration, L7 Long Horizon,
L8 Multimodal, L9 Computer Use. Suites map to layers; a model may run a
subset without invalidating the rest.

## Key invariants

- `raw -> never edited, derived -> regeneratable` (SPEC 33): any harness
  correction creates a new run under `results/raw/RUN-ID/`.
- Harness + model = evaluation unit (SPEC P2): every manifest records
  model, harness/prompt hashes, backend, sampling, and runtime versions.
- Deterministic oracles first (SPEC P6): Tier 1 oracle > execution >
  AST diff > trajectory rules > LLM judge.
- Failure is data (SPEC P7): every scored failure carries exactly one
  primary failure (DEN C25) plus optional secondary tags (C26).
