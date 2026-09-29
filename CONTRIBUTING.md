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

## Good first issues (start here — all labeled `good first issue`)

1. **LangGraph general-agent adapter** — mirror
   `adapters/forge_agent_emo_x.js`: wrap `shared/run.py` as a LangGraph
   tool node, record harness spec next to results. No scoring changes.
2. **Arabic vision task (V7)** — add a second Arabic fixture
   (`vision-bench/fixtures/make_fixtures.py` generates PNGs; no Pillow
   needed at runtime) + `ground_truth.json` keywords + oracle test.
   Follow the V3 pattern.
3. **qwen3-2b vs llama3.1:8b on code25** — run both via Ollama
   (3 trials, same seed), submit sealed bundles under
   `results/community/` per its README. No code, pure measurement.
4. **Third agent-loop scenario** — copy the `ledger/` pattern in
   `suites/agent-loop/episode.py`: new repo + bug class + oracle tests
   + manifest, registered in `SCENARIOS`. shop/ stays frozen.
5. **Health-board widget** — add one panel to
   `shared/render_health_board.py` (e.g. per-model validity table).
   HTML/CSS only, no deps.

Bigger threads are labeled `help wanted` (multi-repo AgentLoop,
hidden-suite rotation, contamination canary expansion). Ask in
Discussions before large PRs.

## Local-only files (never push these)

`AGENTS-X.md`, `FINAL-REPORT.md`, `PLAN-Y.md`, `REVIEW-X.md`, and
`reports/*.md` (except `reports/BASELINE_*.md`, the published
baselines) are **maintainer-local working documents**: they live in
your checkout via `.git/info/exclude` but must NEVER be tracked. CI
fails any PR that tracks them. `PLAN-X.md` (Master Plan) is the only
internal doc that ships with the repo.
