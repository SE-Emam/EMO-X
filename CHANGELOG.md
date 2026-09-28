# Changelog — EMO-X

All notable changes to this project are documented here.
Versioning rules: `SPEC.md` §45 (PATCH = semantics-preserving fixes;
MINOR = new optional suites/metrics; MAJOR = task/oracle/scoring/
prompt/harness changes + mandatory re-baseline).

## [Unreleased] — v2.0.0-rc1 (Adaptive Agent Evaluation)

### Added
- `pip install emo-x-eval` (Track 1): `pyproject.toml` + `src/emox/`
  (`emo` entry, lazy API, tree resolution via EMOX_ROOT/bundled
  data/live checkout) with build-time data bundling (`setup.py`,
  `MANIFEST.in`); single-version lock test across pyproject, runner,
  MCP server, and SKILL frontmatter.
- Hero splash (`shared/splash.py`): large centered blue ASCII logo on
  stderr every run (`--quiet` silences; NO_COLOR/non-tty safe),
  dynamic version/suite/manifest/test counts, compact fallback under
  60 columns; surfaced in MCP `initialize.serverInfo`, forge `splash`
  action, and the SKILL session opening.
- `suites/issues/` (IS1 csv-quoted-commas, IS2 config-deep-merge,
  IS3 backoff-cap, IS4 url-join-slash, IS5 budget-sum-check,
  IS6 json-required-keys, IS7 dedup-order, IS8 utc-offset-sign,
  IS9 ttl-expiry): GitHub-issue-style repair tasks with a
  SWE-bench-shaped oracle — visible fixture tests plus held-out hidden
  tests executed post-episode and deleted unseen; PASS needs fixture
  green AND hidden green AND FINAL stop. Registered in runner + CLI.
- Live progress (`shared/progress.py`): suite/attempt bar + current
  step title + pass/fail tallies + elapsed/approximate ETA on stderr
  (`--no-progress` disables); MCP `notifications/progress` via
  `progress_token`; progress never touches scored events (bundles
  byte-identical on/off).

### Added (P1 conformance — external review)
- Canonical bootstrap inputs (`scoring.family_value_lists`,
  `family_strict_lists`, `instance_mean_scores`): one implementation
  behind every CI; report CIs estimate the family-balanced pass rate.
- Instance-level pairing (`scoring.instance_paired_bootstrap` with
  family fallback flagged in `pairing_level`/`n_paired`); compare output
  carries both fields.
- Leaderboard comparability gate: bands only within strict B58 +
  material-caps classes; lone/conditional entries are report-only
  (`ranked: false`, SVG shows "report-only").
- Formal `terminal_state` (`CLEAN_STOP` iff FINAL + verified green +
  zero pending + zero forbidden) driving A14.
- Second agent-loop family AG2 (`ledger/` pagination-boundary repo)
  behind a scenario registry (`SCENARIOS`, `scenario_for`); shop/
  prompts and IDs byte-frozen. New runner executor
  (`suites/agent-loop/executor.py`, families AG/AG2) registered in
  `SUITE_DIRS`; manifests `AG.json` + `AG2.json`.
- `runner.run_suite` forwards `force=` to supporting executors.

### Added (P2 — external review: integrity, aging, multimodal)
- Hidden suite doubled: HH4 (lcm), HH5 (base digit-sum), HH6
  (multiples sum) with manifests; every hidden prompt carries a
  digit-free canary tag (oracle-regex-safe; training presence proves
  leakage).
- Contamination monitoring wired: per-family (canonical, novel) pairs
  feed `contamination_snapshot` (global + by-task); unknown (never 0)
  without novel evidence.
- Aging automation wired: per-task `saturation_snapshot` across
  reference models; `rotation_candidates` = saturated ∪
  high-contamination tasks.
- `shared/render_health_board.py`: HTML + JSON health dashboard
  (validity, rotation candidates, per-task saturation/contamination/
  flakiness/discrimination).
- Vision V6 (conjunctive red-squares counting, reuses grid fixture +
  ground truth); SKILL + manifests + oracle tests updated.
- `time_horizon_fit` reports `converged` (non-convergent fits are
  invalid, never silent); `max_iter` override for tests.
- `adapters/event_steps.py`: single canonical JSONL event normalizer
  behind opencode/pi adapters (equivalence-pinned, standalone-safe).

### Added (engineering roadmap: numeric, contracts, DX, adapters, perf)
- `BOOTSTRAP_MAX = 100_000` DoS cap with `ValueError` on bad B;
  antisymmetric pairing pinned by property test.
- `tests/scoring/test_api_contract.py`: public surface, stdlib-purity,
  determinism, NA-convention pins.
- `Makefile` (`gate/selftest/suites/scans/clean`) + `.pre-commit-config.yaml`.
- `adapters/_base.py`: shared `final_diff`/timeout/decode helpers;
  opencode/pi delegate (probe/argv/prompts stay per-adapter by design).
- Streaming bundles: `BundleStream` writes per-attempt lines, publishes
  once (rename+seal); length-mismatch fails closed; crash leaves no
  partial RUN dir. Rejected with reasons in ARCHITECTURE.md: parallel
  calls, ScoringContext DI, SQLite index.

### Fixed (Scoring/Reporting Conformance Pass — external review P0)
- Version synchronized to `2.0.0-rc1` (single source
  `shared/runner.py`; pyproject, emox, MCP server, SKILL frontmatter,
  CITATION.cff, README roadmap, CHANGELOG follow); splash frame now
  widens to fit the version string (frame invariant preserved).
- `BOOTSTRAP_RESAMPLES = 10_000` single source in `shared/scoring.py`;
  all report paths consume it (no more hardcoded B=1000).
- New `shared/invariants.py` (JSON Schema + Semantic Validator =
  contract): PASS⇒1, non-pass⇒0, PARTIAL middle, FAIL⇒failure label,
  unique C4 identity, trial/variant integrity; enforced at the
  `build_v2_report` gate. The gate caught a real runner bug: the
  variant loop never forwarded `variant=` so multi-variant suites
  emitted duplicate C4 identities (fixed in `shared/runner.py`).
- Tool Discipline wired into the report from canonical per-attempt
  components (`scoring.tool_components_from_agent_attempt`); Robustness
  rebuilt from canonical RB1/RB2 signals
  (`scoring.robustness_from_drift`) with `robustness_signals` detail
  block; both NA (never 0) when unobservable.
- A7 recovery made genuine: fault + recorded post-fault recovery +
  green verification (BACKEND_ERROR excluded); fault-free episodes no
  longer earn recovery credit.
- One runner contract: `security-bench/run_security.py` and
  `vision-bench/run_vision.py` are thin wrappers over
  `runner.run_suite` (standard sealed bundles); `runner.run_suite`
  forwards `force=` to supporting executors; `emo`≡`run.py` pinned
  by contract test.

### Fixed (from live-data audit)
- Independent audit follow-up: removed one dead code line
  (`run_agent_suite` unused dict), one dead import (`bench_lib` in
  `hermes_adapter.py`), fixed `REVIEW-X.md` stale test count
  (214 → 505, AST-counted), clarified `variant_for_difficulty`
  D6/D7→novel mapping in docstring, added 12 `adaptive.py` tests
  (previously untested), hardened CI with compileall + secrets scan
  + dangerous-pattern guard.
- Follow-up audit, items 1–4:
  - `cat` in `safe_tool_run` now logs `ctx.reads` (unified trail with
    `tool_read`) and caps content at 6000 chars with `...[truncated]`
    (memory/context bound).
  - Legacy `bench_lib` executors (`run_py`, `run_py_file`, `run_js`,
    `run_rust`, `verify_tsc`, `psql_query`, `verify_patch`) now spawn
    with proxy-stripped env (`_clean_env`), matching the documented
    network-off policy.
  - `_SAFE_ARG_RE` tightened (`@` dropped; `:` kept — pytest node IDs
    like `file::test` are legitimate, shell=False renders all inert).
  - `Ctx`/`_safe`/`tool_*` deduplicated into `shared/agent_tools.py`;
    `shared/run.py` and `suites/agent-loop/episode.py` import the same
    objects (divergence now fails tests, not silently).
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
- `tests/`: 680 tests (harness 260, generators 67, scoring 192,
  golden 30, backends 131) + `tests/run_all.py` unified runner.
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
