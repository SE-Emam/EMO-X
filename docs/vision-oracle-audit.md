# Vision Oracle and Fixture Audit (V1–V12)

**Scope:** deterministic code/fixture integrity only. This document does not claim real-model visual accuracy and does not replace independent visual review of each image against its ground truth.

## Family map

| Family | Current oracle | Main limitation / follow-up |
|---|---|---|
| V1 — UI grounding | Bounding-box IoU against frozen normalized coordinates | IoU validates geometry against stored GT, not that the GT itself matches the pixels. |
| V2 — Toolbar grounding | Bounding-box IoU against frozen normalized coordinates | Same GT limitation; verify color/label target visually during an independent fixture review. |
| V3 — Arabic OCR | Required normalized keyword presence | Not exact transcription; can accept extra, reordered, or contextually wrong text if all keywords appear. |
| V4 — Shape counting | Exact integer count | Deterministic count oracle; real-model count accuracy requires later live runs. |
| V5 — Toolbar counting | Exact button count, excluding search field | Target definition depends on visual annotation and must remain explicit. |
| V6 — Red-square count | Exact integer count | Color/shape categories need stable fixture definitions. |
| V7 — Image difference | Required target keywords plus target-clause contradiction/competing-attribute checks | A bounded deterministic heuristic, not general visual-semantic understanding. Oracle code is included in the harness hash. |
| V8 — Spatial relation | Required relation alias and no competing relation; one-word answer contract | Strictly follows the current prompt. It does not evaluate broader scene graphs or multiple relations. |
| V9 — Chart reading | Exact integer for the target color | Depends on chart GT and axis interpretation; live model accuracy remains unmeasured. |
| V10 — Noisy grounding | Bounding-box IoU against frozen normalized coordinates | Noise robustness is not proven until real-model trials; GT still needs independent visual review. |
| V11 — Dense counting | Exact integer count including partially occluded shapes | Tests one frozen scene; it is not a general occlusion benchmark. |
| V12 — Table extraction | Exactly two parseable integers (rows, amount), both exact | Now rejects extra integers as INVALID rather than accepting the first two values. |

## Engineering changes in this phase

- **V12 false positive fixed:** the old oracle accepted any response whose first two numbers matched, even if the response added unrelated numeric claims despite the prompt requiring only two integers. The oracle now requires exactly two parseable integers; V12 manifest is version 1.1.
- Added a deterministic regression test for an extra integer in the V12 response.
- Added fixture-integrity tests for all 12 test cases and every frozen fixture hash recorded in `ground_truth.json`.
- Added internal ground-truth consistency checks for normalized boxes, V7 target keywords, chart target value, table row count/amount, Arabic keywords, and V8 relation vocabulary.
- The Vision harness fingerprint includes the delegated `vision-bench/run_vision.py` implementation, so oracle edits change provenance.

## What fixture integrity does and does not prove

The test verifies that fixture files exist, are valid PNGs, match their recorded SHA-256 values, and agree with key structural relationships in ground truth. It **does not** prove the visual annotations are correct by inspecting the pixels. That requires an independent visual review of every fixture, including noisy/dense images and the Arabic card.

## Remaining work

1. Independently inspect each frozen image against its ground truth and record reviewer/evidence without rewriting existing fixture hashes silently.
2. Add adversarial positives/negatives to V3, V7, V8, and V12 where output format or keyword presence can mislead the oracle.
3. Review IoU thresholds and invalid/VOID classification for unsupported image input and payload-size failures.
4. After development gates close, run approved live-model trials and report per-family accuracy, false positives/negatives, and repeatability. These experiments are intentionally deferred.
