# Vision Sprint 1 Implementation Report — 2026-10-09

## Summary

Implemented the approved Sprint 1 quick-wins from
`docs/vision-development-plan.md` §3.5 (harden oracles, decouple
provenance, first perturbed robustness). No new task families were
added, frozen prompts (`P_GROUND` / `P_ARABIC` / `P_COUNT`,
`PROMPT_PACK vision-v1`) were not changed, and the fail-closed
two-stage vision gate semantics were preserved (VOID never FAIL on
image-blind endpoints).

The vision inventory stays at 6 families (V1–V6). V4/V5 gain a second
`perturbed` variant (same count oracle, noisy fixture); V1/V2/V3/V6
stay canonical-only.

## Changes

- `shared/scoring.py`: canonical `normalize_arabic` (tashkeel-stripped,
  alef/ة-normalized), `normalize_int` (digits, Arabic-Indic digits, EN
  words, AR words), `iou_tier` (0.5/0.7/0.9). `vision-bench/run_vision.py`
  mirrors them locally to stay stdlib-only standalone.
- `vision-bench/run_vision.py`: `judge_arabic` is now normalized
  substring order-free over 6 keywords; `judge_count` uses
  `normalize_int` with `INVALID_NO_INT` vs `WRONG_RESULT (off_by_1)`
  split; grounding logs raw `iou` + `iou_tier`; `PERTURBED_IMAGE_MAP`
  routes `grid_count.png` / `ui_toolbar.png` to perturbed siblings
  (counts unchanged).
- `suites/vision/executor.py`: exact `FAMILY_TEST_MAP` dispatch
  (replaces `startswith` + `sorted[0]`); `VARIANTS =
  (canonical, perturbed)` with `PERTURBED_FAMILIES = (V4, V5)`;
  count failures split into `INVALID_NO_INT` (INVALID) vs
  `WRONG_RESULT (off_by_1)` (FAIL); `prompt_pack_sha256` covers both
  perturbed PNGs.
- `vision-bench/fixtures/make_fixtures.py`: deterministic perturbed
  makers (`make_grid_perturbed`, `make_toolbar_perturbed` + seeded
  speckle) and per-fixture `fixture_sha256` recording.
- Fixtures + ground truth: `grid_count_perturbed.png` (7/4 unchanged),
  `ui_toolbar_perturbed.png` (3 unchanged), `arabic_card.png` keywords
  2 → 6 (`تسجيل، الدخول، مرحبا، المتجر، زر، أحمر` — functional test
  data), `fixture_sha256` map for all 6 PNGs.
- Manifests V1–V6: `fixture_sha` filled; V1/V2 oracle notes
  `iou_tier` logging; V3 oracle notes 6-keyword normalized check;
  V4/V5/V6 oracles note `normalize_int` + `off_by_1`/`INVALID` split;
  V4/V5 declare `perturbation` block + `variants:
  [canonical, perturbed]`.
- `vision-bench/SKILL.md`: fixtures, oracle, and verification sections
  updated to match the implementation above.
- Tests: `tests/backends/test_vision_executor.py` (+10: 6-keyword
  pass/partial-fail/normalized-alef, word-form, Arabic-Indic,
  off-by-one fingerprint, INVALID, exact map, V4/V5 perturbed,
  perturbed-rejected); new `tests/scoring/test_vision_norm.py` (11:
  arabic/int/tier units).

## Verification

| Check | Result |
|---|---|
| `python3 tests/run_all.py` | PASS — all 5 suites green (harness 324, generators 82, scoring 210, golden 30, backends 148; total 794) |
| `unittest discover -s tests/scoring` | PASS — 210 tests OK (incl. 11 new `test_vision_norm`) |
| `unittest discover -s tests/backends -p "test_vision*"` | PASS — 21 tests OK |
| `pytest tests/backends/test_realworld_vision.py` | PASS — 7 tests OK |
| Fixture SHA cross-check (`ground_truth.json` vs bytes vs manifests) | PASS — all 6 PNGs `GT_OK`, V1–V6 `fixture_sha` match |
| `ruff check` on touched Python files | PASS — no findings |
| Frozen prompts unchanged | PASS — `P_GROUND`/`P_ARABIC`/`P_COUNT` byte-identical to plan baseline |

## Follow-up notes

- S1 scope intentionally excluded V1/V2 paraphrase referents and the
  V10 noisy-grounding family; they remain S1-future / S2 work per the
  plan table.
- V7 multi-image (schema `image_count:2` + multi-message executor)
  remains the S2 blocker; S3 density/docs/partial-credit stays behind
  the `partial_curve` opt-in flag.
- `python3 -m ruff format --check` still reports pre-existing style
  drift (6 files, incl. untouched regions); not reformatted here to
  keep the diff reviewable — same posture as the `bb96352` style fix.
