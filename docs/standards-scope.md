# Scope, standards, and why the final report is trustworthy

Answers to the three standing questions.

## 1. Is there one unified global performance standard?

**No.** The field is fragmented by modality by construction: 282+
unique benchmarks (ALL-Bench) / 447+ (BenchLM) across 486 models and
22 providers. Text, vision, embeddings, decisions, images, video, and
audio measure incommensurable quantities — a single number across them
would be numerology, not science.

EMO-X does not claim the unified standard. It claims a **bounded,
auditable scope**:

| Layer | EMO-X covers | External standard (use it, not us) |
|---|---|---|
| Code/agent execution + trajectory + health | ✅ suites, sealed bundles, CIs | SWE-bench/Terminal-Bench (ecological validity) |
| Embeddings | ❌ refused + pointer | MTEB / BEIR / MIRACL |
| Decision models (Jev: Choice/Score/Noul) | ❌ refused + pointer | TypeSafe internal benchmarks |
| Image/video/audio/CNN/RL | ❌ refused + pointer | FID / VBench / LibriSpeech / ImageNet / Atari |

Refusal with a pointer is a feature: it keeps EMO-X numbers inside
the domain where they mean something.

## 2. Does the baseline depend on the EMO-X evaluation?

Yes — deliberately and transparently. A baseline number is a
**harness+model joint measurement** (PLAN §0.2), recorded with the
full harness spec (prompts bytes, tool list, stop rule, budget, exact
argv, backend capabilities, model modalities). Change any of it and
the B58 comparison key changes: the runs become NON-COMPARABLE by
rule, not by opinion. Dependence is total and explicit — which is
exactly what makes the numbers checkable instead of vibes.

## 3. What makes the final report reliable? (proofs, not promises)

1. **Sealed provenance** — `seal.json` per bundle; tampering breaks
   verification (`verify_bundle_seal`). Reports cite bundle IDs.
2. **Frozen inputs** — PROMPT_PACK hashes; any prompt change voids
   comparability automatically (B58).
3. **Statistical honesty** — paired bootstrap 95% CIs (B=10,000),
   no fixed gap rules, `significant/directional/inconclusive` only.
4. **Semantic gate** — `shared/invariants.py` rejects malformed raw
   (PASS+0.4, duplicates, missing failure labels) loudly.
5. **Capability gating** — modality/type gates refuse incapable
   models pre-call; scored zeros from them are inadmissible.
6. **Self-audit** — saturation/flakiness/contamination monitors can
   disqualify the benchmark's own tasks (rotation candidates).
7. **Fail-closed safety** — scope gates, VOID/ERROR taxonomy,
   unknown-CSV ineligibility.
8. **Reproduction recipe** — every report carries seed, trials,
   versions, and exact commands (`docs/model-onboarding.md` §3).

A report lacking any of 1–4 is not an EMO-X result; it is an anecdote.
