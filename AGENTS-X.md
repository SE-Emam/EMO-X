# EMO-X — Executive Agents Plan

> Agents work in parallel via the `Task` tool. Each agent exclusively owns
> its files (§3). The `X-0` monitor runs continuously and holds veto power
> on contract breaks.

---

## 1. Roster

| Agent | Role | Phase | Work packs |
|---|---|---|---|
| **X-0 Monitor** | monitoring + QA + conflict prevention | ongoing (α→2.0) | all WPs (read-only + veto) |
| **X-1 Contracts** | contracts: schemas, manifests, results layout, self-test, sandbox | α first (opens the road) | WP1, WP2 |
| **X-2 Generators** | Task DSL + deterministic generation + mutations + PROMPT_PACK_v2 | α (after WP1) | WP4 |
| **X-3 Scoring** | scoring engine + metrics + golden tests (Parts B+C) | α (after WP1) | WP3, WP6 |
| **X-4 Suites** | Core-25 + agent-loop + security migration to `suites/` | α→β (after WP1,WP2) | WP5 (+β: WP7–WP10 suites) |
| **X-5 Integration** | health + adaptive + CLI + v2 report + long-horizon + gauntlet | β→2.0 (after WP3) | WP11–WP15 |

---

## 2. Parallelism DAG

```text
Batch 0 (immediate, parallel):  X-1 starts contracts
                                 X-0 starts monitoring (baseline: v1 self-test green?)
Batch 1 (after schemas/manifests frozen):
                                 X-2  ┐
                                 X-3  ├─ fully parallel (separate files)
                                 X-4  ┘  (X-4 also needs WP2 for execution)
Batch 2 (after WP3 green):  X-5 health/adaptive/CLI
Batch 3 (2.0):              X-5 gauntlet/long-horizon + remaining X-4 suites
```

Rule: no agent waits for another inside the same batch — dependencies are
only on the frozen Batch-0 contracts.

---

## 3. File ownership (exclusive — writing outside is forbidden)

| Agent | Owns for writing | Read-only |
|---|---|---|
| X-1 | `shared/schemas.py`, `shared/manifests.py`, `shared/sandbox.py`, `shared/safety.py`, `results/` layout, `tests/harness/` | SPEC Parts A |
| X-2 | `generators/*`, `prompts/PROMPT_PACK_v2.md`, `prompts/SHA256SUMS`, `tests/generators/` | `shared/schemas.py` |
| X-3 | `shared/scoring.py`, `shared/metrics.py`, `judges/*`, `tests/scoring/`, `tests/golden/` | DENOMINATORS §§C1–C93 |
| X-4 | `suites/*`, `tests/backends/` (migration) | `shared/sandbox.py`, `shared/schemas.py` |
| X-5 | `health/*`, `shared/adaptive.py`, `shared/runner.py`, `shared/run.py` (CLI), `docs/*`, v2 report | everything above (read) |
| X-0 | writes no code; writes `reports/QA_X*.md` only | everything |

---

## 4. Handoff protocol between agents

1. X-1 publishes the **frozen contracts**: `schemas.py` (§C83 fields + `run_manifest.json` §32) + `manifests.py` (Task DSL §7). Any later change = version bump.
2. X-3 publishes the **denominator registry** as importable code (§C81) + the edge-case table (§C82) as tests — X-4/X-5 import it, never reinvent it.
3. X-2 publishes the **determinism key**: `seed → instance_hash` (`generators/seeds.py`) — X-4 uses it for every new instance.
4. Handoff = files + green tests + one line in `PLAN-X.md` §4 checklist. Without that, acceptance is refused (X-0).

---

## 5. X-0 monitor powers (instant veto on)

- Writing outside ownership (§3) or touching a frozen contract (PROMPT_PACK_v1, REPORT v1, `EMO{SYNTH_…}`).
- A scoring formula with no golden test or no `D=0 ⇒ NA` coverage.
- Merging `ERROR/VOID` into a performance denominator (§C9) or double-counting within one axis (§C77).
- Displaying a number with no CI/Coverage/Health (§B60).

Monitor report: `reports/QA_X_<date>.md` (violations + per-WP status + bottlenecks).

---

## 6. Ready-to-launch tasks (paste into the Task tool)

### X-0 — Monitor (launch first, runs for the whole project)

```text
Role: EMO-X QA monitor (read-only over code, write-only reports/QA_X_*.md).
Loop: (1) verify PLAN-X.md §4 checklist per WP, (2) grep for contract breaks
(frozen: PROMPT_PACK_v1, REPORT_TEMPLATE v1, EMO{SYNTH_), (3) run
python shared/run.py --self-test + pytest tests/ when present,
(4) report violations with file:line. You own no product files and change none.
Stop rule: report INSUFFICIENT_EVIDENCE rather than guessing (DEN §C88).
```

### X-1 — Contracts & Sandbox (Batch 0)

```text
Build per SPEC §§32-35 + DEN §§C4,C83: shared/schemas.py (attempt/instance/
manifest/run_manifest JSON schemas with negative tests), shared/manifests.py
(Task DSL §7 manifest loader+validator), shared/sandbox.py + shared/safety.py
(sandbox_only, forbidden paths, fail-closed), results/raw|derived/ layout (§33).
Write tests/harness/. Frozen touch ban: PROMPT_PACK_v1, REPORT_TEMPLATE,
report.py output line. Done = --self-test green + schemas reject bad logs.
```

### X-2 — Generators (Batch 1, needs X-1 schemas)

```text
Build per SPEC §§7-8: generators/task_dsl.py, instance_factory.py, mutations.py,
seeds.py (deterministic seed→instance + instance_hash/oracle_hash), canonical→
novel variant classes (§9), prompts/PROMPT_PACK_v2.md + SHA256SUMS. Golden rule:
same seed on two machines → identical hashes. Write tests/generators/.
Never embed expected answers in generators (§6).
```

### X-3 — Scoring Engine (Batch 1, needs X-1 schemas)

```text
Implement shared/scoring.py + shared/metrics.py + judges/ per SPEC Part B
(B4-B63) and DEN Part C (C9-C93) EXACTLY. Import-first: build the denominator
registry (C81) as importable code. Every formula gets a golden test in
tests/golden/ incl. full edge table C82 with D=0⇒NA (never 0). Aggregation
order: Attempt→Instance→Variant→Task→Capability (C78). Primary labels mutually
exclusive; secondary tags may overlap (C25-C26). Done = all goldens green.
```

### X-4 — Suites Migration (Batch 1, needs X-1 + X-2 input)

```text
Migrate legacy suites to suites/ as canonical task families with Task DSL
manifests: code-bench-25 (25 families from shared/run.py t*/r*/h*), agent-loop
(run_agent episode), security (fixtures incl. EMO{SYNTH_} UNCHANGED), vision,
computer-use. Use X-2 seeds for instance ids, X-1 schemas for outputs, X-3
registry for scores — reimplement nothing. Keep legacy files runnable until
α-gate. Done = --suite code25 green on new layout with raw/ manifests (§32).
```

### X-5 — Health/Adaptive/CLI/Report (Batch 2, needs X-3 green)

```text
Build health/ (saturation/discrimination/flakiness/contamination per C48-C53,
C69-C72), shared/adaptive.py (D0-D7 controller §10), new CLI flags per SPEC
§42 (--suite dynamic-code/recovery/gauntlet/profile, --self-test, --health),
docs/*.md, and the v2 capability-profile report (§§43-44, B60-B61: profile+
fingerprint+efficiency+uncertainty, never one number). Safety gate CSVRate=0
(B56) enforced. Done = --health + full profile run with CI+coverage+health.
```

---

## 7. Proposed launch sequence

1. Launch **X-0** first (establishes the baseline).
2. Launch **X-1** (Batch 0).
3. On contract freeze: launch **X-2 + X-3 + X-4** in parallel.
4. On WP3 green: launch **X-5**.
5. X-0 delivers `reports/QA_X_*.md` after every batch.
