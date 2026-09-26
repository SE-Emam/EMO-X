# Contributing — EMO-X

## Golden rules (from `PLAN-X.md` §0)

1. **Contracts first:** no new code before freezing the contract it
   depends on (`shared/schemas.py`, `shared/manifests.py`).
2. **Golden tests first:** every scoring formula gets a golden test from
   `SPEC.md` Part B / `DENOMINATORS.md` Part C before adoption —
   including the `D=0 ⇒ NA` edge row.
3. **Raw is immutable:** never edit `results/raw/`; fixes create new runs.
4. **Frozen is frozen:** `PROMPT_PACK_v1`, `REPORT_TEMPLATE v1`,
   `EMO{SYNTH_…}` format — changes require a version bump + re-baseline.

## Workflow

- Stdlib only for the core (no new dependencies without a recorded decision).
- Pure scoring functions with docstrings citing `B/C` section numbers.
- Run `python3 tests/run_all.py` and `python3 shared/run.py --self-test`
  before every push — both must be green (`REVIEW-X.md` R1).
- Reports go in `reports/` (git-ignored `*.md`); run bundles in
  `results/raw/RUN-ID/` (git-ignored, structure kept via `.gitkeep`).

## Adding a suite

See `docs/adding-a-suite.md`: Task DSL manifest + canonical instances
(deterministic seeds) + raw-only executor + schema-validated outputs.
