# code25 Sprint 2 Implementation Report — 2026-10-08

## Summary

Added the secure SQL repair family T30, resilient API client family T33, and
safe SQLite migration family T36. Expanded T2, T3, R2, and R5 with fixed
perturbed variants. New generated-code execution remains inside the shared
fail-closed, network-isolated Docker sandbox; T33 and R5 use injected mock
transports/clients rather than external services.

The code25 inventory is now 32 families. T30, T33, and T36 each have
deterministic positive and negative golden coverage. T33 also verifies
no-retry and retry-on-4xx negative behavior; T36 rejects destructive
table-recreation and syntax-error candidates.

## Changes

- Added `T30.json`, `T33.json`, and `T36.json` manifests with Python
  execution, 30-second execution budgets, deterministic execution oracles,
  disabled network access, and sandbox-only filesystem policy.
- Added canonical prompts and execution oracles for the three new families.
- Added `perturbed` prompts and production runner dispatch for T2 edge cases,
  T3 multiple-bug repair, R2 JOIN/NULL/duplicate handling, and R5 pagination
  and error propagation.
- Added real Docker-backed T30/T33/T36 oracle tests and Docker-backed
  perturbed-variant checks, including an isolated Node mock for R5.
- Updated manifest/inventory tests, `code-bench-25/SKILL.md`, README counts,
  and this development plan's Sprint 2 status.
- Refreshed the README test badge to 769 tests.

## Verification

| Command | Result |
|---|---|
| `make gate` | Passed: Docker sandbox image built, harness self-test passed, and all five unified test groups passed. PostgreSQL self-test was skipped because the local `psql` environment lacked a local user ID 501. |
| `uv run --frozen pytest tests/generators/test_all_families_golden.py -v` | Passed: 10 tests and 83 subtests, including all three new families and expanded variants. |
| `uv run --frozen pytest tests/backends/test_manifest_truth.py tests/backends/test_suites.py -v` | Passed: 22 tests and 298 subtests; all 32 manifests and canonical prompts match the inventory. |
| `uv run --frozen python tests/run_all.py --count` | Passed: harness 324, generators 78, scoring 199, golden 30, backends 138; 769 total tests. |

No Sprint 3 families or executor-wide refactor were included.
