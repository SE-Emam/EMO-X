# code25 Sprint 3 Implementation Report — 2026-10-08

## Summary

Added T31 algorithmic-complexity repair, T32 multi-file repository feature,
and T34 async concurrency safety. The code25 inventory now contains 35
families. Sprint 3 changes preserve the shared fail-closed Docker boundary;
no external network access or LLM judging is used.

## Oracle design

- **T31:** Deterministic inputs at sizes 100, 1,000, and 10,000; three
  measured calls per size; exact distinct counts required on all trials.
  Every 10,000-item call must finish in less than 0.5 seconds. Empty and
  duplicate-heavy edge cases are also checked. A counted integer subclass
  also enforces a deterministic equality/order-operation budget to reject
  quadratic implementations even when host timing variance is favorable.
- **T32:** The executor writes `text_utils.py`, authoritative
  `tests/test_text_utils.py`, and `README.md` into a fresh Docker sandbox.
  It replaces only the implementation file with the model answer and runs
  pytest in that workspace. The tests and README are not model-writable.
- **T34:** One hundred `asyncio.gather` updates use amounts 1 through 100.
  The provided task induces deterministic interleaving with
  `await asyncio.sleep(0)` between read and update. A lock-protected solution
  must end at 5050; an unprotected implementation loses updates.

## Golden coverage

Each family has a positive canonical implementation and two negative cases:

- T31: set-based O(N) implementation passes; quadratic baseline fails the
  10,000-item time bound; incorrect counts fail correctness.
- T32: tag normalizer passes the sandbox pytest suite; syntax errors and
  behavior that violates tests are rejected.
- T34: `asyncio.Lock` implementation passes; deterministic unlocked race
  and an implementation raising during increment both fail.

Focused tests execute the real oracle in Docker. The all-family fixture test
uses deterministic backend stubs, consistent with existing suite patterns.

## Changed files

- `suites/code-bench-25/manifests/T31.json`
- `suites/code-bench-25/manifests/T32.json`
- `suites/code-bench-25/manifests/T34.json`
- `suites/code-bench-25/cases.py`
- `suites/code-bench-25/executor.py`
- `tests/generators/test_all_families_golden.py`
- `tests/backends/test_manifest_truth.py`
- `tests/backends/test_suites.py`
- `code-bench-25/SKILL.md`
- `README.md`
- `docs/code25-development-plan.md`
- `docs/code25-sprint3-report.md`

## Verification

The tagged, unrelated `T37.json` was temporarily moved out of the manifest
directory while these commands ran, then restored unchanged. It remains
untracked and excluded from this Sprint 3 change set, as approved.

- `uv run --frozen pytest tests/generators/test_all_families_golden.py::test_t31 -v` — passed (1 test).
- `uv run --frozen pytest tests/generators/test_all_families_golden.py::test_t32 -v` — passed (1 test).
- `uv run --frozen pytest tests/generators/test_all_families_golden.py::test_t34 -v` — passed (1 test).
- `uv run --frozen pytest tests/generators/test_all_families_golden.py -v` — passed (16 tests, 95 subtests).
- `make gate` — passed: all five unified test groups green; generators 81,
  scoring 199, golden 30, and backends 138. PostgreSQL self-test skipped
  because the local `psql` environment lacks a local user ID 501.
- `uv run --frozen pytest tests/backends/test_manifest_truth.py -v` — passed
  (7 tests, 175 subtests).
- `uv run --frozen python tests/run_all.py --count` — passed with 772 tests
  total (harness 324, generators 81, scoring 199, golden 30, backends 138).

The operation-budget hardening was added after an initial timing-only run
showed the O(N^2) negative fixture could cross the 0.5-second threshold in
one run and slip below it in another. The final T31 focused command passed
three consecutive runs after this guard was added.
