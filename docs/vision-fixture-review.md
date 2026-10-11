# Vision Fixture Ground-Truth Review Matrix

**Purpose:** human, pixel-level review of frozen Vision fixtures against `vision-bench/fixtures/ground_truth.json`.
**Current state:** `PENDING HUMAN REVIEW`. Hash and structural tests are not visual evidence. Do not mark a row PASS without inspecting the rendered image.
**Guardrails:** do not edit fixture pixels, annotations, hashes, or manifests as part of review. Any correction needs a separate reviewed change, rationale, updated SHA-256, and provenance/version update.

## Review matrix

Review the embedded image at native scale where possible. For boxes, compare the GT box (normalized by `box_scale=1000`) to the actual target bounds; for perturbed/noisy fixtures, verify the stated transformation preserves target identity and count. Record reviewer, date, evidence, and final status in the last column.

| Fixture | Expected ground truth to inspect | Status / reviewer / evidence |
|---|---|---|
| [ui_login.png](../vision-bench/fixtures/ui_login.png) ![ui_login.png](../vision-bench/fixtures/ui_login.png) | Red LOGIN, green Cancel, blue Help; white search and username fields; button count = 3; all five normalized boxes and labels. | **PENDING** — not independently visually verified |
| [ui_login_noisy.png](../vision-bench/fixtures/ui_login_noisy.png) ![ui_login_noisy.png](../vision-bench/fixtures/ui_login_noisy.png) | Same target boxes/colors/count as ui_login; Gaussian noise/blur and side/corner occlusion must not obscure or change targets. | **PENDING** — not independently visually verified |
| [ui_toolbar.png](../vision-bench/fixtures/ui_toolbar.png) ![ui_toolbar.png](../vision-bench/fixtures/ui_toolbar.png) | Blue SAVE, gray Settings, red Delete, white search field; button count = 3; four normalized boxes and labels. | **PENDING** — not independently visually verified |
| [ui_toolbar_perturbed.png](../vision-bench/fixtures/ui_toolbar_perturbed.png) ![ui_toolbar_perturbed.png](../vision-bench/fixtures/ui_toolbar_perturbed.png) | Same toolbar targets and count as ui_toolbar; stated +6px-equivalent redraw/speckle must preserve target identity and bounds within the expected tolerance. | **PENDING** — not independently visually verified |
| [arabic_card.png](../vision-bench/fixtures/arabic_card.png) ![arabic_card.png](../vision-bench/fixtures/arabic_card.png) | Confirm rendered Arabic text reads “تسجيل الدخول”, “مرحبا بك في المتجر”, “زر الدخول أحمر”; verify listed keywords and reading order/rendering. | **PENDING** — not independently visually verified |
| [grid_count.png](../vision-bench/fixtures/grid_count.png) ![grid_count.png](../vision-bench/fixtures/grid_count.png) | Blue circles = 7; red squares = 4; total shapes = 11. Count every visible target once. | **PENDING** — not independently visually verified |
| [grid_count_perturbed.png](../vision-bench/fixtures/grid_count_perturbed.png) ![grid_count_perturbed.png](../vision-bench/fixtures/grid_count_perturbed.png) | Same counts as grid_count despite seeded speckle, small shifts, and color variation; ensure no speckles resemble target shapes. | **PENDING** — not independently visually verified |
| [grid_dense.png](../vision-bench/fixtures/grid_dense.png) ![grid_dense.png](../vision-bench/fixtures/grid_dense.png) | Blue circles = 12; red squares = 6; total = 18; partially occluded shapes still count; gray bars are occluders, not target shapes. | **PENDING** — not independently visually verified |
| [spatial.png](../vision-bench/fixtures/spatial.png) ![spatial.png](../vision-bench/fixtures/spatial.png) | Red circle above blue square; verify geometry and Arabic relation target “فوق”. | **PENDING** — not independently visually verified |
| [chart.png](../vision-bench/fixtures/chart.png) ![chart.png](../vision-bench/fixtures/chart.png) | Blue = 4, red = 7, green = 3 on a 0–10 y-axis; target red value = 7; inspect bar heights and axis ticks. | **PENDING** — not independently visually verified |
| [table_orders.png](../vision-bench/fixtures/table_orders.png) ![table_orders.png](../vision-bench/fixtures/table_orders.png) | Headers ITEM/QTY/AMOUNT; rows A(2,20), B(1,35), C(4,15); 3 data rows excluding header; item C amount = 15. | **PENDING** — not independently visually verified |
| [diff_a.png](../vision-bench/fixtures/diff_a.png) ![diff_a.png](../vision-bench/fixtures/diff_a.png) and [diff_b.png](../vision-bench/fixtures/diff_b.png) ![diff_b.png](../vision-bench/fixtures/diff_b.png) | Compare the pair side-by-side: the only intended difference is the middle square changing from blue to red; positions and sizes must remain unchanged. | **PENDING** — not independently visually verified |

## Review record

| Field | Value |
|---|---|
| Reviewer | PENDING |
| Review date | PENDING |
| Method / display scale | PENDING |
| Fixtures PASS | 0 / 12 |
| Corrections needed | PENDING |
| Unresolved | 12 / 12 until a reviewer records evidence |

## Important interpretation

- This matrix is a review aid, not evidence that the annotations are correct.
- A fixture can be marked **PASS** only after a reviewer visually compares the pixels to the listed ground truth and records concise evidence.
- Use **CORRECTION NEEDED** when pixels and annotation conflict; use **UNRESOLVED** when the image is ambiguous or cannot be inspected adequately.
- Keep historical result bundles and frozen evidence untouched. If a correction is warranted, open a separate issue/PR and rerun the deterministic Vision fixture-integrity and test groups.
- Real-model/provider trials remain outside this review.
