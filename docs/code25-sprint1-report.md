# code25 Sprint 1 Implementation Report — 2026-10-08

## Summary

Completed the Sprint 1 T9 calibration regression, canonical golden replies
for all 29 families, documentation count refresh, and stricter R4/R13
structural oracles. No new task families were added, `executor.py` was not
refactored, and the Docker sandbox policy was not changed.

## Changes

- Added `tests/generators/test_t9_calibration.py` to run all 16 T9 calibration
  samples against `check_family("T9", ...)`.
- Added `tests/generators/test_all_families_golden.py` with positive and
  negative canonical replies for all 29 families, H3-only variant inventory
  checks, and focused malformed/semantically-wrong R4/R13 cases.
- Updated R4 to parse the JSON configuration and require a supported
  catch-all source with the exact `/index.html` destination.
- Updated R13 to parse a conservative Dockerfile instruction subset,
  including backslash continuations and JSON-array instructions, and check
  the requested Python base, workdir, requirements copy, pip install, CMD,
  and base-tag constraints. This is not a full BuildKit parser.
- Updated R4/R13 manifest oracle descriptions.
- Updated code25 family-count wording in the skill page, README, report
  template, and relevant tests/history notes. README generated metrics now
  report 765 test functions.
- Made the R10 `useState`, `onClick`, `setCount`, `Counter`, and export
  checks case-insensitive, and added realistic mixed-case and lowercase
  regression examples.

The golden tests call the production family oracles. For execution-backed
families, they replace external sandbox/runtime calls with deterministic
fixtures that only return a passing result for the exact known-good source.
This keeps the tests fast and avoids executing generated code on the host;
it does not replace real sandbox integration verification.

## Verification

| Check | Result |
|---|---|
| `uv run --frozen pytest tests/generators/test_t9_calibration.py -v` | Passed: 1 test, 16 calibration subtests. |
| `uv run --frozen pytest tests/generators/test_all_families_golden.py -v` | Passed: all golden/parser tests; 29 families each have positive and negative cases. |
| Combined new regression tests | Passed: 6 golden tests plus 1 T9 calibration test; 69 golden subtests and 16 calibration subtests. |
| `uv run --frozen pytest tests/backends/test_manifest_truth.py -v` | Passed: 7 tests, 145 subtests. |
| `uv run --frozen pytest tests/backends/test_suites.py -v` | Passed: 15 tests, 132 subtests with Docker sandbox active. |
| `uv run --frozen python tests/run_all.py --count` | Passed: harness 324, generators 74, scoring 199, golden 30, backends 138; total 765. |
| `FAMILY_IDS` / manifest inventory check | Passed: 29 families and 29 manifests match. |
| Ruff check | Passed: no findings. |
| Ruff format check | Passed: 204 files already formatted. |
| Scoped Mypy | Passed: 3 source files. |
| README metric freshness and `git diff --check` | Passed: README reports 13 suites and 765 tests; no whitespace errors. |
| `make gate` | Passed with Docker active: sandbox image built, self-test passed, all five test groups green. PostgreSQL self-test was skipped because the local scratch service was unavailable. |

## Follow-up notes

- PostgreSQL-specific self-test coverage remains environment-dependent; the
  local scratch PostgreSQL service was unavailable in this run.
- Historical documents retain the original “25” count only where explicitly
  marked as the migration-time count or original product name.
