# EMO-X — Development Plan (Master Development Plan)

> **EMO-X = Adaptive Agent Evaluation** — the adaptive generation of EMO
> (methodology stays: Execution • Measurement • Observability).
> Normative reference: `SPEC.md` (Parts A+B) + `DENOMINATORS.md` (Part C, §§C1–C93).
> Reference release strategy: `SPEC.md` §46.

---

## 0. Golden rule

1. No new code before freezing the contract it depends on.
2. Every scoring formula gets a golden test taken from `SPEC.md` Part B and `DENOMINATORS.md` Part C before adoption.
3. `raw → never edited, derived → regeneratable` (§33): any fix = new run, never edited results.
4. Frozen contracts are untouchable: `PROMPT_PACK_v1`, `REPORT_TEMPLATE v1` + `report.py:86`, the `EMO{SYNTH_...}` format.

---

## 1. Starting point (Legacy Inventory)

| Current component | State | Fate in EMO-X |
|---|---|---|
| `shared/run.py` (monolith, ~835 lines: 25 tests + agent loop + CLI) | works (v1) | split into `shared/runner.py` + `suites/` + `generators/` |
| `shared/bench_lib.py`, `backends.py` | works | reorganized: execution into `sandbox.py`, connectivity into `backends.py` |
| `shared/report.py` (v1 contract) | frozen | stays; the v2 report is built beside it, not over it |
| `code-bench-25/`, `agent-loop-bench/`, `security-bench/`, `vision-bench/`, `computer-use-bench/`, `adapters/` | working SKILLs + fixtures | migrated to `suites/*/` as canonical samples + task manifests (Task DSL §7) |
| flat `results/*.json` | v1 | replaced by `results/raw/RUN-ID/` + `results/derived/RUN-ID/` structure (§33) |
| `SPEC.md`, `DENOMINATORS.md`, `PLAN.md` | documented | `SPEC.md`+`DENOMINATORS.md` = the reference; `PLAN.md` = v1 archive |

---

## 2. Target architecture (SPEC §41 — condensed for execution)

```text
EMO-X/
├── shared/        # bench_lib, backends, runner, schemas, scoring,
│                  # metrics, manifests, sandbox, safety, adaptive, run
├── prompts/       # PROMPT_PACK_v1 (frozen) + PROMPT_PACK_v2 + SHA256SUMS
├── suites/        # code-bench-25, agent-loop, dynamic-code, recovery,
│                  # robustness, security, calibration, long-horizon,
│                  # vision, computer-use  (+ gauntlet in v2.0)
├── generators/    # task_dsl, instance_factory, mutations, seeds
├── judges/        # deterministic, execution, trajectory, llm_judge
├── health/        # saturation, discrimination, flakiness, contamination
├── tests/         # harness, generators, scoring, backends, golden
├── results/       # raw/ + derived/
└── docs/          # architecture, task-dsl, metrics, backend-contract,
                   # security-model, adding-a-suite, benchmark-health
```

Binding migration map:

| From (legacy) | To (EMO-X) |
|---|---|
| `shared/run.py:run_code25` + `t*/r*/h*` functions | `suites/code-bench-25/` manifests + cases (canonical instances) |
| `shared/run.py:run_agent_suite/run_agent` | `suites/agent-loop/` |
| `security-bench/` fixtures + `run_security.py` | `suites/security/` + `judges/` |
| `shared/bench_lib.py` executors | `shared/sandbox.py` + `judges/execution.py` |
| `results/*.json` results | one-shot migration into `results/raw/` (the `migrate_v1.py` tool) |

---

## 3. Phases (matching §46)

### Phase α — executive foundation (v2.0-alpha)

| WP | Pack | Inputs | Outputs (files) | Acceptance |
|---|---|---|---|---|
| WP1 | Contracts and schemas | SPEC §§32–34, DEN C4,C83 | `shared/schemas.py`, `shared/manifests.py`, `results/raw|derived/` layout | JSON schema rejects a record missing `trial_id` (negative test) |
| WP2 | Isolation + Self-Test | SPEC §§24,35 | `shared/sandbox.py`, `shared/safety.py`, green `--self-test` | `run.py --self-test` fails closed (fail-closed) on sandbox break |
| WP3 | Scoring engine + goldens | SPEC Part B, DEN Part C | `shared/scoring.py`, `shared/metrics.py`, `tests/golden/` | every B6–B63 and C9–C93 formula has a golden test; `D=0 ⇒ NA` covered (full §C82) |
| WP4 | Task DSL + deterministic generation | SPEC §§7–8 | `generators/*.py`, `prompts/PROMPT_PACK_v2.md` + `SHA256SUMS` | same seed yields same `instance_hash` on two machines |
| WP5 | Core-25 migration | WP1,WP2 | `suites/code-bench-25/` (25 families × canonical at planning time; now 29) | 29/29 run via `--suite code25` + immutable raw results |
| WP6 | Failure taxonomy + fingerprint | SPEC §30, DEN C25–C27 | `judges/trajectory.py` (initial) | every scored failure carries one `primary_failure` (C25) |

**α exit gate:** full `code25` on the new structure + green golden tests + `run_manifest.json` (§32) per run.

### Phase β — agent and behavior (v2.0-beta)

| WP | Pack | Outputs | Acceptance |
|---|---|---|---|
| WP7 | Recovery + fault injection (§§13–14) | `suites/recovery/`, `judges/*` recovery | Recovery Rate computed on `D_recoverable` only (C29) |
| WP8 | State Drift + Plan Staleness (§§15–16) | `suites/robustness/` (state-drift) | `D_drift=0 ⇒ NA`, not 100% (C58) |
| WP9 | Tool Discipline (§§17–19) | `shared/metrics.py` (TD) | non-applicable component = excluded from geometric mean (C41) |
| WP10 | Calibration + Abstention (§§21–22) | `suites/calibration/` | Brier and ECE on `D_cal` only (C50) |
| WP11 | Benchmark Health (§§11–12, C48–C53,C69–C72) | `health/*.py` + `--health` | `<5 models ⇒ Discrimination=NA` (C70) |

**β exit gate:** `agent-loop` + `recovery` + `calibration` work; report shows a Capability Profile, not one number (§§55–61).

### Phase 2.0 — adaptation and long horizon

| WP | Pack | Outputs | Acceptance |
|---|---|---|---|
| WP12 | Adaptive Difficulty (§10) | `shared/adaptive.py` | D0–D7 ability curve instead of a fixed point |
| WP13 | Long Horizon (§§25–26) + Time Horizon (B46) | `suites/long-horizon/` | `β≥0 ⇒ time-horizon invalid` (B46) |
| WP14 | Gauntlet (§28) | `suites/gauntlet/` | compound scenario with ≥7 entangled dimensions |
| WP15 | Official 3-trial baseline + public validation | `docs/`, official report | Coverage≥95% + `n≥3` + safety gate (§B56) |

### Phase 2.1 — conformance era (v2.0.0-rc1, core plan — not addenda)

Roadmap items discovered mid-build are folded here as first-class
phases (a comprehensive study would have placed them upfront; they
are recorded as plan, not patches):

| WP | Pack | Outputs | Acceptance |
|---|---|---|---|
| WP16 | Version/uncertainty conformance | `BOOTSTRAP_RESAMPLES`, `invariants.py`, report gate | B=10k everywhere; malformed raw rejected |
| WP17 | Tool/robustness wiring | canonical components + `robustness_signals` | NA never 0; signals exposed |
| WP18 | Runner unification | standalone wrappers, `force=` | one contract, all bundles sealed |
| WP19 | Bootstrap/pairing/leaderboard | canonical builders, instance pairing, comparability gate | conditional never ranked |
| WP20 | Agent scenarios + clean stop | AG2 ledger, `terminal_state`/A14 | shop frozen byte-identical |
| WP21 | Integrity + aging + multimodal | HH4–HH6 + canary, health wiring + board, V6 | hidden doubled, rotation flags |
| WP22 | Hardening + community | run-id entropy, redaction, atomicity, SSRF, H3-exp, constants, templates, R3 script | auditor PASS |
| WP23 | Model types + modalities | `MODEL_TYPES` (13→19), stages, `--model-type`, onboarding | out-of-scope refused with pointer |
| WP24 | Agent frameworks | generic CLI adapter, framework matrix | probe-gated, NON-COMPARABLE |
| WP25 | Product UX | README fold, GIF, unified progress + SVG chart | 60-second trial, single bar |

---

## 4. Global acceptance criteria (apply to every WP)

- [ ] stdlib only for the core (no new dependencies without a recorded decision).
- [ ] every scoring function: pure + golden test + `D=0 ⇒ NA` case.
- [ ] no number displayed without `95% CI` (bootstrap over Task Family — B54), Coverage, and Health.
- [ ] DIRECT comparison only on matching `PromptHash+HarnessHash+ManifestHash` (§B58).
- [ ] any change to (task/oracle/scoring/prompt/harness) = version bump + re-baseline (§45).

---

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Breaking the v1 freeze during migration | legacy keeps working until the α gate; migration is additive, not replacing |
| Golden tests written after the code (confidence forgery) | contracts and goldens written first (WP1→WP3 before WP5) |
| Write conflicts between agents | exclusive file ownership per agent (`AGENTS-X.md` §3) |
| Safety treated as a compensatory dimension | mandatory `CSVRate=0` gate (§B56) + monitor review |

---

## 6. EMO-X naming log (executed)

- `EMO-Benchmark-Skills` / `EMO Benchmark Skills` / `emo-bench` → `EMO-X` / `emo-x` in: README, INSTALL, LICENSE, PLAN, SPEC (title + §41 tree), DENOMINATORS (title + lineage), `shared/*.py` (docstrings), `hermes_adapter.py`, the three Arabic SKILLs.
- **Deliberately frozen (untouched):** `PROMPT_PACK_v1.md`, `REPORT_TEMPLATE.md`, the `report.py:86` output line, formula identifiers (`EMO_…`), `EMO-Core-25`, `EMO Gauntlet`, `EMO{SYNTH_…}`, `EMO trace JSON`.
- Remaining external step: renaming the GitHub repo + work folder (needs git/GitHub — not done here).
