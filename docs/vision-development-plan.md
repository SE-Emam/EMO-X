# Vision Suite Development Audit & Plan — 2026-10-08

## Scope and method

Read-only audit of `suites/vision/` + `vision-bench/`. Inspected executor (218 lines), 6 manifests, runner (414), fixture generator (403), SKILL.md (133), ground_truth, backend tests, shared scoring/sandbox/runner, task-dsl/status/metrics/arch docs. No edits, no runs, no model calls.

Current: **6 families, canonical-only**: V1-V2 grounding, V3 Arabic, V4-V6 counting (V6 conjunctive). All synthetic deterministic Pillow fixtures. All oracles deterministic. Fail-closed two-stage vision gate (VOID never FAIL on image-blind endpoints).

## Phase 1 — Discovery

### 1.1 File inventory

| File | Lines | Purpose |
|---|---|---|
| `suites/vision/executor.py` | 218 | Suite executor: gate + family dispatch + raw attempt (no scoring). |
| `suites/vision/manifests/V1-V6.json` | 46-47 ea | Task identity, capabilities, oracle summary, timeouts, weights. |
| `vision-bench/run_vision.py` | 414 | Runner + oracle lib: prompts, gate, IoU/arabic/count judges. |
| `vision-bench/fixtures/make_fixtures.py` | 403 | Deterministic Pillow generator (only PIL importer). |
| `vision-bench/SKILL.md` | 133 | Skill: gate, fixtures, frozen prompts, verification. |
| `vision-bench/fixtures/ground_truth.json` | 1.7K | Boxes 0-1000, Arabic lines/keywords, counts, font/engine. |
| `ui_login.png` | 4.1K | Synthetic 800x600 login (LOGIN/Cancel/Help). |
| `ui_toolbar.png` | 3.8K | Synthetic toolbar (SAVE/Settings/Delete + search). |
| `arabic_card.png` | 14K | Synthetic Arabic card, 3 lines, logical-order GT. |
| `grid_count.png` | 4.8K | Synthetic grid: 7 blue circles + 4 red squares fixed. |
| `tests/backends/test_vision_executor.py` | 130 | Gate + oracle + hash tests. |
| `tests/backends/test_realworld_vision.py` | 89 | Realworld + vision gate/oracle cross-check. |

`__pycache__` bytecode excluded (runtime cache).
## 1.2 Manifest analysis (V1-V6)

Common: category vision, suite vision, prompt_pack vision-v1, version 1.0, capabilities [multimodal + skill], execution {harness suites/vision/executor.py, type vision}, generator {type frozen-canonical, seed 2560X}, variants [canonical], oracle {type deterministic}, scoring {correctness 1.0}, timeouts 60/120, network.allowed false, filesystem.sandbox_only true, difficulty.adaptive false, human_minutes 5. Base difficulty 2 (V1-V5), 3 (V6).

| ID | Name | Capability | Oracle check | Fixture |
|---|---|---|---|---|
| V1 | ground_login | visual_grounding | IoU>=0.5 login box, iou_pass 0.5 | ui_login.png |
| V2 | ground_save | visual_grounding | IoU>=0.5 save box, iou_pass 0.5 | ui_toolbar.png |
| V3 | arabic_read | arabic_ocr | all GT keywords transcribed | arabic_card.png |
| V4 | count_circles | visual_counting | integer == blue_circles (7) | grid_count.png |
| V5 | count_toolbar_buttons | visual_counting | integer == toolbar_button_count (3) | ui_toolbar.png |
| V6 | count_red_squares_conjunctive | visual_counting+attribute_conjunction | integer == red_squares (4) | grid_count.png |

Schema gap: no modalities/image_count/box_scale/fixture_sha fields. Modality implicit via capabilities=[multimodal] + execution.type=vision + SUITE_MODALITIES. Multi-image not declarable today.

## 1.3 Executor analysis

Images: base64 data-URL single image_url part via img_data_url + vision_messages (stdlib only, PIL forbidden in runner). Transport via shared/backends.make_chat -> chat(messages) -> (text, seconds, usage). Frozen prompts: P_GROUND JSON x,y,w,h 0-1000, P_ARABIC lines-only, P_COUNT single-integer. TEMP 0.2 MAX_TOKENS 512.

Extraction: parse_box first-4-floats as x,y,w,h else x_min/y_min/x_max/y_max or left/top/width/height else bare array; judge_arabic all(k in reply); judge_count first -?\d+ == expected.

PASS/FAIL: grounding box!=None and iou>=0.5 (raw iou/pred/expected logged); arabic zero-missing; count exact equality. PASS->1.0 FAIL->0.0 WRONG_RESULT, no PARTIAL. Unparseable box = FAIL not INVALID. build_tests 6 tuples, executor filters startswith(family)+sorted[0] = 1 test/family.

Sandbox: no model code exec, no Docker on vision path. Isolation = network false + sandbox_only + fixture reads + model-endpoint-only net. Two-stage gate: advisory GET models token scan (SSRF-guarded, 0.3s) + binding 1x1 probe. Fail->VOID vision-gate, eligible False. force=True bypass -> ERROR never FAIL. NO_IMAGE_RE reclassifies mid-run image rejection as VOID.
## 1.4 Variants

V1 login grounding: canonical only, frozen coords, synthetic UI. V2 save grounding: canonical only, denser toolbar. V3 arabic: canonical only, single font RAQM/fallback. V4 circles: canonical only 7+4 fixed. V5 toolbar count: canonical only reuse toolbar (3). V6 conjunctive: canonical only reuse grid (4). Zero perturbed/novel/adversarial. Zero multi-image/chart/relation/table. 6 families x1 variant =6 attempts default.

Fixture reuse: toolbar V2+V5, grid V4+V6. Total ~27K PNG. Economical but coupled invalidation.

## 1.5 Scoring

Binary 1.0/0.0, no PARTIAL, no checkpoints. Eligible task_score/pass_rate/efficiency True, calibration False. VOID excluded DEN C5/C9. Aggregation Attempt->Instance->Variant->Task->Capability via shared scoring/denominators. task_score=canonical rate today. human_minutes 5 each max 30. Metadata: run/model/family/instance V*-canonical-001/variant/trial/status/score/eligibility/seed/reasoning/log[:500]/sample[:600]/manifest_sha + response messages/reply/usage/vision_log + bundle prompt/harness/manifest B58. Raw iou/pred/got/hits preserved but not scored. usage passthrough, seconds not per-attempt. Fingerprint WRONG_RESULT only.
## Phase 2 — Gap analysis

### 2.1 Coverage matrix (REAL)

| Skill | Tasks | Depth | Gap? |
|---|---|---|---|
| UI grounding single IoU | V1 V2 | Basic-Intermediate 2 referents fixed IoU0.5 | Yes: tolerance ladder distractors paraphrase small-box |
| Counting single-attr | V4 V5 | Basic static exact first-int | Yes: occlusion density off-by-one |
| Conjunction color+shape | V6 | Intermediate 1 conj anti-shortcut | Yes: only 1 need matrix |
| Arabic printed | V3 2kw 3 lines 1 font | Basic substring order-free | Yes: layout diacritics dense handwriting-look |
| Multi-image compare/diff | None | None | Critical gap |
| Spatial relational | None | None | Critical gap |
| Chart/graph values | None | None | Critical gap |
| Document/table cells | None | None | Critical gap |
| Adversarial perturbed | None | None | Critical gap |
| Dense small-object | None | None | Gap |
| Referring paraphrase | None templated labels | None | Gap |
| Output-contract robust | implicit malformed->FAIL | Basic | Gap conflates instruction+vision |
| Calibration abstention | None | None | Future |
| Temporal video | None | None | Roadmap |

### 2.2 Strengths

1 Deterministic oracles end-to-end IoU/keyword/exact, no LLM-judge SPEC P6.
2 Fail-closed gate hint+probe VOID-never-FAIL SSRF-guarded NO_IMAGE_RE force->ERROR.
3 Sealed provenance prompt+harness+manifest B58 fixtures bytes covered.
4 Programmatic Pillow deterministic no-download no-PII font/engine recorded DEGRADED marks V3 inadmissible.
5 Clear modality SUITE_MODALITIES unified runner bundles report_v2 raw iou preserved.

### 2.3 Weaknesses ranked

1 Multi-image Critical Hard: zero 2+ image diff/coref/state-track, cannot separate captioning from agentic memory.
2 Spatial Critical Medium: no left-of/above/nearest, absolute IoU memorizable, GT multi-box already enables relations.
3 Chart Critical Medium: no bar/line/pie, counts do not transfer to axes/legends.
4 Perturbed Critical Easy/Med: canonical-only memorizable 7/4, novelty C/P/N NA, need Pillow transforms + paraphrase.
5 Counting brittle High Easy: seven fails, 5 vs 700 identical, need word/digit norm OFF_BY_ONE INVALID split.
6 Arabic narrow High Medium: 2kw 1 font short, need 6kw normalization dense paragraph.
7 Reuse+dispatch Medium Easy: shared PNGs coupled, startswith+sorted[0] drops extras, need explicit map + fixture_sha.
### 2.4 Structural observations

- Fixture size healthy ~27K, no bloat. Risk opposite: too clean white-bg large targets, low ecological validity.
- Oracle brittleness: count needs Arabic-numeral int, seven fails but 7 buttons passes; grounding any-4-floats forgiving yet unparseable=FAIL not INVALID mixes instruction+perception; arabic diacritic/case sensitive no normalization alef-hamza flake.
- Manifest schema gaps: no modalities/image_count/box_scale/fixture_sha/tolerance/perturbation blocks. Multi-image + perturbed not declarable without overload.
- Dispatch fragility: startswith+sorted[0] assumes 1:1, silent drop on growth. Need explicit FAMILY_TEST_MAP.
- Scoring ceiling: binary-only raw IoU unused, no PARTIAL curve, no calibration. Fine gates weak leaderboards.
- Provenance gap: prompt_pack covers prompts+GT+fixtures but not make_fixtures.py bytes; font fallback only via string not hash.
- No sandbox risk today (no code exec). Future click-action needs Docker + validation spike.## Phase 3 — Development plan

### 3.1 Design principles

1 Deterministic first bounded judge only with schema. Paraphrase varies prompt never grader. No open LLM-judge without frozen rubric + audit >=0.90.
2 Programmatic GT byte-sealed. Every image generatable Pillow fixed seeds no-net no-PII. GT alongside PNGs. prompt_pack_sha covers new prompts+GT+bytes.
3 Grounding IoU tolerance ladder not string match. Raw IoU always, verdict 0.5 today, roadmap 0.25/0.5/0.75 PARTIAL. Small boxes center-distance aux.
4 Gate fail-closed perturbed fair. New families inherit gate VOID. Perturb preserves solvability human-check + golden, unsolvable rejected at gen never FAIL.
5 One primary variant per instance C/P/N triple. Follow mutations levels canonical->perturbed->novel. Vision novelty_robustness computable Sprint2.
### 3.2 Proposed new task families (6)

V7 Multi-image diff: skill multi-image compare/coref. modality text+image+image 2 PNGs. Two toolbars same layout one button swapped deterministic. Prompt which label changed ONLY + count changed 0/1/2. GT by diffing params. Tests state track minimal memory. Oracle deterministic exact-label lower alias + exact-count both pass. Why: zero 2-image today, agents diff before/after each step. Effort Hard (schema image_count:2 multi-messages 5MB guard GT diff).

V8 Spatial relation: skill relational. modality text+image reuse login+toolbar no new PNG. Is HELP left of LOGIN yes/no + nearest search label. GT from existing boxes deterministic x-compare Euclidean. 3 probes majority. Oracle bool/label exact lower alias. Why: absolute IoU memorizable, relations transfer OSWorld next-to/inside. Effort Medium.

V9 Chart bars: skill chart axes/legend. modality text+image new chart_bars.png Pillow 4 bars heights=f(values 20/45/30/55) ticks. What value green ONLY int + which color largest ONLY name. GT=params not pixels. Oracle exact int +-0 (+-1 PARTIAL roadmap) + exact color. Why: dashboard BI lives charts counts do not transfer. Effort Medium.

V10 Perturbed grounding: skill robustness same V1 harder input. modality text+image deterministic transform ui_login_noisy.png seeded jitter +10pct corner occlusion avoiding target >=95pct visible else reject. Same P_GROUND V1. Oracle IoU>=0.5. Why: first P-level proves not memorization unblocks C/P. Effort Medium.

V11 Dense occluded count: skill counting occlusion density amodal. modality text+image new grid_dense.png 12 blue 6 red 3 occluded gray bars after shapes GT unchanged. How many blue visible incl partial ONLY int. Oracle exact + off-by-one aux. Why: V4 clean-room real UI overlap clutter. Effort Medium.

V12 Table extraction: skill document rows/cells key-value. modality text+image new table_orders.png Pillow 4x3 header deterministic. AMOUNT O-3 ONLY int + rows excl header ONLY int. GT=params. Oracle exact ints. Why: invoice/admin read tables no current structured doc. Effort Medium.

Roadmap out: video 3+ frames handwriting full-Arabic-doc click-action Docker.

### 3.3 Enhancements existing

V1/V2 paraphrase referents same box + small-box center<=50 aux. Easy.
V1/V2 multi-threshold 0.25/0.5/0.75 log verdict 0.5 B58 stable. Easy.
V3 keywords 2->6 arabic norm alef/diacritic dual strict/loose + dense 6-line novel. Medium.
V4/V5/V6 number-words ar-indic norm OFF_BY_ONE INVALID vs FAIL split. Easy.
V4/V6 density sweep novel new positions/counts canonical 7/4 frozen. Medium.
All log oracle_version+fixture_sha8 manifest generator.parameters fixture_sha256 decouple shared. Easy.
All explicit FAMILY_TEST_MAP raise ambiguous. Easy.
### 3.4 Infrastructure changes

1 Manifest schema additive backward-compat: modalities [text image], image_count default1, box_scale 1000, fixture_sha256, tolerance {iou_pass count_tolerance text_norm}, perturbation {kind seed guard}. Update schemas.validate_task_manifest + task-dsl.md + example. V1-V6 defaults fill.
2 Executor multi-image: vision_messages_multi(prompt,[img1 img2]) ordered parts size guard total b64 ~5MB else VOID-infra never FAIL; build_tests images list; run_family passthrough. Required V7 rest single path.
3 Scoring utils pure: iou center_distance normalize_arabic normalize_int relation left-of/above/nearest with unit tests later. No LLM helper.
4 Fixture pipeline: extend make_fixtures make_chart make_dense make_table perturb_login + --only; record generator_bytes_sha + per-fixture SHA ground_truth + SHA256SUMS checked prompt_pack_sha. Pillow-only deterministic no-net.
5 Golden audit: per new family pos+neg goldens tests/backends/test_vision_v7_v12.py later; normalization stability order-swap verbosity transliteration. Must-have before close.
6 Sandbox no change S1-2 vision call-only no Docker. S3 click spike Docker run_in_sandbox + box validation tracked not committed.

### 3.5 Priority timeline

| Sprint | Focus | Tasks | Effort |
|---|---|---|---|
| S1 Quick wins 1-2wk | Harden oracles decouple | V1/V2 paraphrase + multi-thresh log; V4/V5/V6 norm OFF_BY_ONE INVALID split; explicit map; per-fixture SHA; V10 noisy single | S-M no break |
| S2 Core 2-3wk | High-impact gaps | V8 relation no PNG + V9 chart new maker + V7 diff schema image_count:2 multi-exec; C/P/N wiring novelty computable | M-H V7 Hard |
| S3 Advanced 3-4wk | Density docs arabic partial | V11 dense + V12 table + V3 dense novel + PARTIAL f(iou) +-1 behind flag; full goldens SHA docs SKILL | M no actions |

Deps: S2 V7 blocks 3.4.1-2. S3 PARTIAL behind scoring.partial_curve opt-in canonical binary default B58 safe.

### 3.6 Success metrics

- 12 families V1-V12 all deterministic zero blind judge; norm maps audit >=0.90.
- All canonical + perturbed/novel (V7 pair). 100pct count/ground/chart/relation/table deterministic.
- Goldens pos+neg all new; prompt+harness stable; per-fixture SHA.
- Gate fail-closed blind stub 100pct VOID 0 FAIL; force ERROR never FAIL.
- Novelty C/P/N computable V1/V4/V10 triple.
- Fixtures <=200K Pillow no-net no-PII; V3 admissible flag enforced DEGRADED.
- Docs SKILL task-dsl updated; per-sprint reports appended mirroring code25-sprint pattern.

## Sprint 1 implementation status — 2026-10-09 (complete)

The approved Sprint 1 quick-wins (§3.5: harden oracles, decouple
provenance, first perturbed robustness) are implemented. Full detail:
`docs/vision-sprint1-report.md`.

| Work item | Status | Implementation |
|---|---|---|
| V1/V2 `iou_tier` logging | Complete | Raw `iou` + tier (0.5/0.7/0.9) logged; verdict still 0.5 (B58 stable); oracle text updated. |
| V4/V5/V6 `normalize_int` + OFF_BY_ONE/INVALID split | Complete | Digits, Arabic-Indic digits, EN/AR words accepted; `off_by_1` logged as `WRONG_RESULT (off_by_1)`, no-int as `INVALID_NO_INT` (INVALID, not FAIL). |
| V3 keywords 2→6 + `normalize_arabic` | Complete | 6 keywords, tashkeel-stripped alef/ة-normalized substring, order-free; `arabic_admissible` gate unchanged. |
| Explicit `FAMILY_TEST_MAP` dispatch | Complete | Exact map covers V1–V6; unknown raises `KeyError`, perturbed outside V4/V5 raises `TypeError`. |
| Per-fixture SHA provenance | Complete | `fixture_sha256` map in `ground_truth.json`; `fixture_sha` in V1–V6 manifests; both perturbed PNGs in `prompt_pack_sha256`. |
| V4/V5 perturbed variants | Complete | `grid_count_perturbed.png` (7/4) + `ui_toolbar_perturbed.png` (3), deterministic seeded speckle; `PERTURBED_IMAGE_MAP` routing, counts unchanged. |
| Golden coverage + docs | Complete | +10 executor tests, +11 scoring unit tests; `SKILL.md` + this report updated. |

Deferred to S2/S3 per §3.5: V1/V2 paraphrase referents, V10
noisy-grounding family, V7 multi-image (`image_count:2`), V8/V9,
V11/V12, PARTIAL curves (behind `partial_curve` opt-in).

## Appendix provenance

Read executor 218 run_vision 414 make_fixtures 403 SKILL 133 V1-V6 46-47 GT tests test_vision_executor test_realworld_vision shared runner sandbox scoring denominators schemas manifests docs architecture status task-dsl metrics adding-suite code25-plan. Not run/modified. Frozen PROMPT_PACK vision-v1 IOU 0.5 TEMP 0.2 MAX 512 counts 7/3/4 keywords test-data box_scale1000 800x600. Plan-only no implementation per mandate.
