# EMO-X v2.0 Development Readiness Plan

## Scope and phase boundary

This plan covers engineering quality and contributor experience before real model/provider trials. Live evaluation and official baseline creation are deliberately deferred until the maintainer authorizes that phase.

## Non-negotiable invariants

- Never edit historical evidence or existing sealed bundles to make checks pass.
- Do not change frozen prompt packs, score weights, or benchmark contracts without a reviewed, versioned change and explicit rationale.
- Unit/golden tests establish implementation behavior, not real-model accuracy.
- Keep S3–S5 authorization gates enforced; no live security trials in this development phase.
- Use small, focused PRs with targeted tests, full CI evidence, and explicit known limitations.

## Ordered work plan

### 00 — Governance and contribution workflow
- [ ] Link all focused issues from the project plan.
- [ ] Require each issue/PR to state scope, acceptance criteria, tests, changed contracts, and evidence.
- [ ] Verify main protection and required Python 3.10/3.11/3.12 harness checks. If automation cannot configure repository rules, leave this gate open and record the owner action.
- [ ] Keep development readiness separate from baseline eligibility.

### 01 — Spanish T37 oracle
- [ ] Audit implementation and tests against issue #13.
- [ ] Add marker-complete but semantically incorrect closure responses for ES-ES, ES-MX, and ES-AR.
- [ ] Cover valid paraphrases, cross-dialect cases, word boundaries, and contradictions.
- [ ] If deterministic checks cannot prove general semantic correctness, narrow the claim in the manifest and documentation rather than overclaiming.
- [ ] Run focused tests and full CI.

### 02 — Security suite engineering quality
Detailed current inventory and known limitations: [Security Oracle Engineering Audit](security-oracle-audit.md).
- [ ] Inventory S1–S5: threat intent, safe behavior, negative cases, oracle limits, sandbox and authorization gates.
- [ ] Test superficial refusal followed by harmful content, safe lookalikes, injection through tool/file outputs, and refusal-vs-utility.
- [ ] Audit PASS/FAIL/VOID/ERROR/INVALID classification and CSVRate denominator/NA handling.
- [ ] Verify S3–S5 authorization is enforced in code; do not run live gated trials in this phase.
- [ ] Run deterministic tests and full CI.

### 03 — Code25 audit (36 current families)
Initial family map and known oracle limitations: [Code25 Oracle Audit](code25-oracle-audit.md).
- [ ] Build a family-by-family audit table covering contract, fixture, positive/negative tests, oracle type, execution, sandbox, manifest, and limitations.
- [ ] Prioritize T30, T33, T36, R13, A16, T37, plus lexical/structural-only oracles.
- [ ] Add false-positive and edge-case tests; use executable checks where the contract requires execution.
- [ ] Verify every manifest maps to a real family and source prompt. Count parity alone is not quality proof.
- [ ] Document unresolved limitations explicitly.

### 04 — Vision engineering quality (V1–V12)
Current V1–V12 strategy, limits, and fixture-integrity checks: [Vision Oracle Audit](vision-oracle-audit.md).
- [ ] Validate fixtures against ground truth: boxes, labels, colors, counts, Arabic text, chart/table values, and diff pairs.
- [ ] Add positive/negative boundary tests for IoU, counting, OCR normalization, spatial relations, diff contradictions, charts, and tables.
- [ ] Review V7 false positives and false negatives; do not reject a correct answer solely because it mentions an unrelated alternate color.
- [ ] Verify image-capability and infrastructure failures classify as VOID/ERROR rather than model failures.
- [ ] Run focused tests and full CI. Real-model accuracy trials are deferred.

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
