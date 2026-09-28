# EMO-X Architecture (short map)

## `suites/` — the canonical suites

Each runnable suite lives in `suites/<dir>/` with an `executor.py` plus
`manifests/*.json`, and is executed **only** through the unified runner
(`shared/runner.py::run_suite` / `run_profile`, surfaced by the
`shared/run.py` CLI). One contract: standard sealed raw bundles under
`results/raw/RUN-ID/` (`manifest.json`, `events.jsonl`,
`responses.jsonl`, `environment.json`), pinned by
`tests/harness/test_runner_contract.py`. Never bypass the runner with a
bespoke harness — cross-harness rows are NON-COMPARABLE.

## `*-bench/` — NOT legacy, NOT deleted

`code-bench-25/`, `agent-loop-bench/`, `computer-use-bench/`,
`security-bench/`, `vision-bench/` are the per-suite homes for
**agent-facing `SKILL.md` docs** (what the suite is, how to run it).
Where a standalone CLI remains (`security-bench/run_security.py`,
`vision-bench/run_vision.py`), it is a **thin compatibility wrapper**
over `runner.run_suite` (review P0-7): same flags, same sealed bundles —
not a fork. Keep these dirs; do not reimplement suite logic inside them
and do not delete them as "legacy".

## Pointer

Full tree: `SPEC.md` section 41 ("Proposed Repository").
Shared engine: `shared/scoring.py` (pure scoring),
`shared/denominators.py`, `shared/manifests.py`, `shared/runner.py`.

## Deliberately rejected (roadmap review, with reasons)

- **Manifest validation "unification" (2.3)** — already single: every
  manifest passes `manifests.validate_task_manifest`, pinned by
  `test_all_manifests_validate` over all 40+ files. Nothing to merge.
- **ScoringContext DI (2.4)** — rejected: scoring functions are pure by
  contract and `shared/constants.py` IS the shared context. Threading
  a config object through ~80 pure functions adds coupling for zero
  behavioral gain.
- **Parallel model calls** — rejected: deterministic sequential
  execution is a reproducibility feature (SPEC 42 seed schedule).
  Parallelism belongs to a future distributed runner, not this one.
- **SQLite results index** — deferred (roadmap marks it optional):
  JSONL bundles + file layout serve current dashboards; revisit when
  a query pattern needs it.
