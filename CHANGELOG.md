# Changelog — EMO-X

All notable changes to this project are documented here.
Versioning rules: `SPEC.md` §45 (PATCH = semantics-preserving fixes;
MINOR = new optional suites/metrics; MAJOR = task/oracle/scoring/
prompt/harness changes + mandatory re-baseline).

## [Unreleased] — v2.0-alpha (Adaptive Agent Evaluation)

### Fixed (from live-data audit)
- SECURITY D1 (critical, proven): `tool_run` executed agent commands
  with `shell=True` behind a prefix check — `ls; <anything>` ran
  arbitrary commands. Replaced with `sandbox.safe_tool_run`: closed
  grammar (ls/cat/pytest/py_compile), shlex parsing, argv exec, no
  shell ever spawned. Both copies (`shared/run.py`,
  `suites/agent-loop/episode.py`) delegate to it; error strings and
  agent-prompt contract unchanged.
- SECURITY D2: `_safe` path check hardened from `startswith` to
  `os.path.commonpath` (sibling-prefix escape closed), both copies.
- `suites/calibration/executor.py`: removed duplicated
  `prompt_pack_sha256` alias line (D3, no behavior change).
- Special-token tails no longer fail correct answers: new central
  `strip_special_tokens()` in `shared/bench_lib.py` (mirrored in
  `suites/code-bench-25/executor.py`, which keeps locals by design),
  applied at the single `check_family` entry point so every family
  benefits (R11/TS, T7/JSON, R2/R12/SQL, R1/Rust, code families).
- Uniform JSON extraction: `extract_json_object()` (first balanced
  span, brace-aware with string/escape handling) replaces the greedy
  `r"\{.*\}"` in T7 and R4 — embedded-JSON acceptance is now one rule.
- Client report auto-fills endpoint (host-only, from result field or
  `OPENAI_BASE_URL`/`BASE_URL`/`AGENT_BASE` env) and hardware (local
  platform string); explicit args still win. `?`/blank rows are gone
  when the data exists.
- S4b oracle measured channel noise, not skill structure: reasoning-model
  `<think>` leaks and role prefixes now stripped (`clean_channel`) before
  the frontmatter check — in both `suites/security/judges.py` and the
  legacy `security-bench/run_security.py`.
- S5d key-echo upgraded to critical: `judge_s5d_opsec` now emits
  `critical_violation` when the model republishes the full secret, wired
  through `suites/security/executor.py` attempts into the CSVRate gate
  (echo ⇒ NOT RANKABLE), not a mere fail.
- Backend capability manifests (SPEC 36): every run records
  `backend_capabilities`; `/v1/chat/completions` equality never implies
  backend equality (`--provider-profile`, DIRECT/CONDITIONAL/NON_COMPARABLE).
- H3 dynamic equations (SPEC 9): `perturbed`/`novel` variants generated
  from `H3.seed` (numbers/names/representation/wording/context) with the
  same oracle kind (unique modular-equation solution); H3 manifest v1.1.
- `RESULT: PASS (all 5 suites green)` gate via `tests/run_all.py`.
- Novelty Robustness (`scoring.novelty_robustness`): harmonic C/P/N.
- Human Time Horizon Lite: `estimated_human_minutes` in 55+ manifests,
  auto-attached by the runner; stub-backend capability fallback.

### Added
- `SPEC.md` Parts A (architecture §§1–50) + B (normative scoring §§B1–B63).
- `DENOMINATORS.md` Part C (§§C1–C93): denominator registry, NA-vs-zero
  rules, overlap resolution, edge-case table.
- `shared/`: `schemas`, `manifests`, `sandbox`, `safety`, `scoring`,
  `metrics`, `denominators`, `adaptive`, `runner`, `report_v2`
  (stdlib only).
- `generators/`: Task DSL, deterministic instance factory, mutations,
  seeds (`seed → instance_hash` reproducible cross-machine).
- `judges/`: deterministic, execution, trajectory (single primary failure),
  llm_judge (reliability-gated).
- `health/`: saturation, discrimination, flakiness, contamination.
- `suites/`: code-bench-25 (25 families), agent-loop, dynamic-code,
  recovery, robustness, security (S1–S5, synthetic fixtures only),
  calibration, long-horizon, gauntlet, vision (real executor over
  vision-bench fixtures), realworld (RW1–RW3 mini-real repos),
  computer-use (PILOT).
- `tests/`: 214 tests (harness 29, generators 44, scoring 96,
  golden 30, backends 15) + `tests/run_all.py` unified runner.
- CLI: `--suite dynamic-code|recovery|gauntlet|profile`,
  `--instances`, `--seed`, `--fault-rate`, `--self-test`, `--health`.
- `docs/`: architecture, task-dsl, metrics, backend-contract,
  security-model, adding-a-suite, benchmark-health.
- Project renamed `EMO-Benchmark-Skills` → **EMO-X**
  (Adaptive Agent Evaluation); license: Apache-2.0.

### Frozen (never edited, only superseded by version bump)
- `shared/PROMPT_PACK_v1.md`, `REPORT_TEMPLATE.md` + `shared/report.py`
  (v1 output contract), `EMO{SYNTH_…}` fixture format.

## [v1.0] — 2026-09-25 — Legacy baseline (archived)
- Monolithic `shared/run.py`: 25 code/tool tests with real execution,
  Batch-4 agent loop (A1–A15), security/vision/computer-use skills,
  frozen `PROMPT_PACK v1`, flat `results/*.json`.
- Kept runnable for reference; see `PLAN.md` (v1 archive).
