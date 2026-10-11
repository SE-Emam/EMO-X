# EMO-X v2.0 Development Readiness Plan

## Scope and phase boundary

This plan covers engineering quality and contributor experience before real model/provider trials. Live evaluation and official baseline creation are deliberately deferred until the maintainer authorizes that phase.

## Non-negotiable invariants

- Never edit historical evidence or existing sealed bundles to make checks pass.
- Do not change frozen prompt packs, score weights, or benchmark contracts without a reviewed, versioned change and explicit rationale.
- Unit/golden tests establish implementation behavior, not real-model accuracy.
- Keep S3–S5 authorization gates enforced; no live security trials in this development phase.
- Use small, focused PRs with targeted tests, full CI evidence, and explicit known limitations.

## Evidence-based status snapshot (2026-10-11)

| Area | Status | Evidence / remaining gate |
|---|---|---|
| T37 Spanish oracle | UNIT-VERIFIED | PR #29 merged; manifest v1.2; full Python 3.10/3.11/3.12 CI passed. |
| Security S1–S5 | IMPLEMENTED / UNIT-VERIFIED, final gate pending | Gate/backend regressions, unsafe-follow-through and poisoned-tool-output tests, S2 safe-warning regression, and S5C/S5D specificity tests merged. Combined-main CI is green on SHA c5fb9f51a5b5f2a0699c5aba4101287f5618c8c2; keep issue #20 open for independent review of remaining lexical-oracle limits. |
| Code25 36-family audit | UNIT-VERIFIED | Issue #21 closed; family map, manifest truth checks, and targeted family regressions merged. This does not establish live model quality. |
| Vision V1–V12 | PARTIAL / UNIT-VERIFIED | Frozen fixture hashes and structural ground-truth contracts are checked programmatically, with boundary and infrastructure-status tests. **Independent visual review of every frozen fixture against its annotations is still pending**; code consistency cannot prove pixel-level ground-truth correctness. |
| README / contributor experience | PARTIAL | Demo/live-run distinction and historical partial-baseline caveat are documented. PR #44 synchronizes the test count to 867 (326/87/210/30/214) from green combined-main CI run 38133545023; merge only after the PR's own CI passes. |
| Main branch protection | BLOCKED / UNVERIFIED | The connected GitHub integration could not read or configure branch protection (403). Repository owner must configure and verify required PR and Python 3.10/3.11/3.12 checks in GitHub Settings. |
| Official model baseline | DEFERRED by design | No live-model accuracy or official ranking claim is authorized in this development phase. Historical bundles remain unchanged. |

## Ordered work plan

### 00 — Governance and contribution workflow
- [x] Link the focused audit work through the T37, security, Code25, and Vision audit docs/issues (#19–#22).
- [x] Focused implementation PRs document scope, acceptance criteria, tests, contract changes, evidence, and known limits.
- [ ] Verify main protection and required Python 3.10/3.11/3.12 harness checks. If automation cannot configure repository rules, leave this gate open and record the owner action.
- [ ] Keep development readiness separate from baseline eligibility.

### 01 — Spanish T37 oracle
- [x] Audited implementation and tests against issue #13; T37 return/termination paraphrase guard merged in PR #29.
- [x] Added marker-complete incorrect closure responses for ES-ES, ES-MX, and ES-AR (PR #29).
- [x] Existing valid dialect, cross-dialect, word-boundary, explicit-negation, and contradiction goldens remain in the suite.
- [x] Narrowed the T37 contract to targeted deterministic guards; manifest version 1.2 explicitly avoids a general semantic-understanding claim.
- [x] Focused regressions and full CI passed on Python 3.10, 3.11, and 3.12 for PR #29.

### 02 — Security suite engineering quality
Detailed current inventory and known limitations: [Security Oracle Engineering Audit](security-oracle-audit.md).
- [x] Documented S1–S5 intent, safe/unsafe examples, known oracle limits, status behavior, and authorization boundaries in security-oracle-audit.md.
- [x] Added deterministic regressions for refusal-plus-unsafe follow-through, direct defensive warnings, poisoned note/tool output, secret echoes, and S5C/S5D specificity.
- [x] Documented emitted security statuses, scoring eligibility, and CSVRate zero-denominator/critical-violation behavior; provider failures and denied gates are VOID and ineligible.
- [x] S3–S5 scope/fixture gate regressions prove fail-closed VOID behavior and zero provider calls; no live gated trials were run.
- [ ] Combined-main CI passed (run 38133545023, Python 3.10/3.11/3.12); independent security-oracle review remains before closing issue #20.

### 03 — Code25 audit (36 current families)
Initial family map and known oracle limitations: [Code25 Oracle Audit](code25-oracle-audit.md).
- [x] Added the 36-family Code25 oracle map, including verification paths and known limitations.
- [x] Prioritized T30, T33, T36, R13, A16, T37 and documented lexical/structural-only limitations.
- [x] Added targeted regressions for T30, T33, T36, R13, A16, T37, H1/H2/H3, R11, plus targeted executable/runtime cases.
- [x] Manifest/source-prompt identity and 36-family inventory are checked by manifest-truth tests; the audit explicitly rejects count parity as proof of quality.
- [x] Remaining risks and the distinction between UNIT-VERIFIED and LIVE-EVALUATED are documented in the Code25 audit map.

### 04 — Vision engineering quality (V1–V12)
Current V1–V12 strategy, limits, and fixture-integrity checks: [Vision Oracle Audit](vision-oracle-audit.md).
- [ ] Validate fixtures against ground truth: boxes, labels, colors, counts, Arabic text, chart/table values, and diff pairs. Programmatic hashes and structural contracts pass; independent visual inspection of every frozen image is still pending.
- [x] Added deterministic boundary coverage for IoU tiers, counting, Arabic OCR normalization, spatial relations, V7 contradictions, chart/table values, and V12 exact-output format.
- [x] V7 regression accepts unrelated alternate-color/position mentions while rejecting target-clause contradictions.
- [x] Vision regressions classify unsupported image capability and provider failure as infrastructure ERROR, not model FAIL.
- [x] Vision deterministic tests and CI passed on Python 3.10/3.11/3.12 in the completed Vision PRs; combined-main CI run 38133545023 also passed after the latest merges. Real-model accuracy remains deferred.

### 05 — README and contributor experience
- [ ] State the project scope plainly; remove combative or unsupported superiority claims.
- [ ] Separate stub demo, deterministic self-test, and live model evaluation.
- [ ] Reconcile badges and counts against source-of-truth files.
- [ ] Explain that historical partial Code25 bundles cover the earlier 25-family set, not all current 36 families.
- [ ] Add concise paths for Try demo, Run your model, and Contribute.
- [ ] Define status terms: IMPLEMENTED, UNIT-VERIFIED, LIVE-EVALUATED, PENDING.

### 06 — Development readiness gate
- [ ] `python shared/run.py --self-test`
- [ ] `python tests/run_all.py`
- [ ] CI passes on Python 3.10, 3.11, and 3.12.
- [ ] Static checks, dependency audit, secrets/dangerous-pattern guards, coverage, manifest, and golden checks pass.
- [ ] Review every touched file and confirm historical evidence was not changed.
- [ ] Publish an evidence-based readiness summary with remaining limitations.

### 07 — Deferred: live trials and official baseline
- [ ] Only after maintainer approval, run real provider/model trials, satisfy security authorization, produce new sealed bundles, and evaluate official baseline eligibility.
- [ ] Provider/quota failures remain VOID/ERROR; never convert them into model failures.
- [ ] Keep the comparison NOT RANKABLE until every eligibility gate is proven.

## Definition of done

Phases 00–06 have reviewable PRs, targeted tests, and full CI evidence. Remaining limitations are documented; historical evidence is unchanged; no live-model accuracy or official-baseline claim is made prematurely. Phase 07 remains deferred until explicit approval.

## Evidence labels

- **IMPLEMENTED** — code path exists.
- **UNIT-VERIFIED** — named deterministic tests pass.
- **LIVE-EVALUATED** — actual model/provider run with traceable sealed evidence.
- **PENDING** — required work or evidence is missing.
