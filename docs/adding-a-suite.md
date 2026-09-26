# Adding a suite

Contract refs: SPEC sections 7 (Task DSL), 32-33 (manifest, raw layout),
45 (versioning: oracle/scoring/prompt/harness change = bump + re-baseline).

## Steps

1. Create `suites/<name>/` with `cases.py`, `executor.py`,
   `manifests/<FAMILY>.json` per family.
2. `cases.py`: `FAMILY_IDS`, `prompt_text`/`prompt_messages`,
   `make_instance` (ids `{family}-{variant}-{index:05d}` via
   `generators/seeds.py`; record the seed), `check_family` returning
   `(passed, log)`, `run_family` returning schema-valid
   `(attempt, response)` via `shared/schemas.py::validate_attempt`.
   Raw records only — no scoring in suites.
3. `manifests/`: one Task DSL JSON per family (see docs/task-dsl.md);
   validate with `shared/schemas.py::validate_task_manifest`.
4. `executor.py`: re-export the suite API plus `prompt_pack_sha256()`
   (over canonical prompts) and `harness_sha256()` (over this file's
   bytes) — the B58 pair. Any prompt/glue change invalidates hashes.
5. Register the directory in `shared/runner.py::SUITE_DIRS` and run:
   `python shared/run.py --suite <name> --backend stub --instances 2`.
6. Confirm the bundle: `results/raw/RUN-ID/{manifest.json (SPEC 32),
   events.jsonl, responses.jsonl, environment.json}`.

## Example suites

`suites/dynamic-code` (parametric + mutations), `suites/recovery`
(fault injection, D_recoverable), `suites/gauntlet` (>=7 dimensions).
