# PLAN-Y — Master Plan for Remaining Work (EMO-X)

> Binding contract for both waves + integration + QA. Every agent reads
> this file first, then `SPEC.md` + `DENOMINATORS.md` for the sections in
> its scope.
> Iron rule: **exclusive file ownership** (§3) — any write outside it = veto.

## 1. Wave 1 — 9 parallel agents (no dependencies between them)

| Agent | Task | Exclusively owned files | Acceptance |
|---|---|---|---|
| Y-1 | Official VOID | `shared/schemas.py` (STATUS_CAUSES + classify_cause + VISIBILITY constants), `shared/manifests.py` (verify_prompt_pack), `docs/status-model.md`, `tests/harness/test_status_model.py` | 7-cause table tested; pack tampering detected |
| Y-2 | Extended self-test | `shared/selftest.py` (new: 14 checks + SKIP), `tests/harness/test_selftest.py` | missing binaries = SKIP not FAIL; tampering = closed FAIL |
| Y-3 | Technical raw immutability | `shared/seal.py` (new: seal/verify/no-overwrite/derived), `tests/harness/test_seal.py` | tampering detected; overwriting RUN_ID refused |
| Y-4 | Hidden suite | `suites/code-bench-25-hidden/*` (new), `docs/contamination.md`, `tests/backends/test_hidden.py` | runtime-only instances; gate refuses without opt-in |
| Y-5 | Official think | `shared/backends.py` (append reasoning_mode_for only), `suites/*/executor.py` mode lines (code25/agent-loop/dynamic), `tests/harness/test_reasoning_mode.py` | every attempt carries a valid mode; mixed-condition comparison labeled |
| Y-6 | Comparison statistics | `shared/scoring.py` (reps flag only), `shared/report_v2.py` (compare/render), `README.md` (3pp removal), `docs/metrics.md`, `tests/scoring/test_compare.py` | 24/25 vs 23/25 = inconclusive/directional, never significant; no "wins" word |
| Y-7 | Security scope-gate | `shared/safety.py` (hardening), `suites/security/executor.py` (new), `security-bench/run_security.py` (S3–S5 gate), `docs/security-model.md`, `tests/harness/test_safety_gate.py` | S3–S5 refuse without approval and never call the model; fixture tampering detected |
| Y-8 | Manifest as source of truth | JSON merges in `suites/code-bench-25/manifests/*.json` (data only) + `tests/backends/test_manifest_truth.py` (prompt equality) | 25/25 byte-identical; no `.py` edits |
| Y-9 | Rebuild remainder | `docs/REPRODUCIBILITY.md` (field list), `tests/harness/test_rebuild_manifest.py` | every field on the list present in a real manifest |

### Cross-cutting contracts (published by owner, consumed by Y-INT)
- Y-1: `classify_cause(cause)->status` + `VoidRun` + `verify_prompt_pack(name)` + `VISIBILITY/normalize_visibility`.
- Y-2: `run_all_checks()->(ok, rows)` in the same shape as `run_self_test` (name, bool, detail + "SKIP: ").
- Y-3: `seal_bundle(rundir)->seal.json` + `verify_bundle_seal(rundir)->bool` + `refuse_overwrite`.
- Y-4: `instance_id` convention + `H3-hidden-*` + `visibility` field in manifests.
- Y-5: `reasoning_mode_for(think, num_predict, native)->mode`.
- Y-6: `compare_models/render_comparison` + `paired_bootstrap_diff(..., return_reps=True)`.
- Y-7: `require_scope_gate(family, scope)` + `ScopeDenied` + `verify_fixture_dir`.
- Y-8: manifests carry the final `prompt` (byte-identical).
- Y-9: final manifest field list.

## 2. Wave 2 — Y-INT (integration, works alone after Wave 1 green)

Exclusively owns: `shared/runner.py` + `shared/run.py` (CLI) + flipping the prompt source to manifests.
Checklist (all mandatory):
1. run_suite: exceptions→VOID (Y-1), self-test delegation to Y-2, seal after writing (Y-3), SUITE_DIRS+gates+claim-tier for hidden (Y-4), reasoning_conditions (Y-5), sampling pass-through (present — verify).
2. run.py: `--hidden-ok` and `--temperature/--top-p/--top-k/--context` flags (provider-profile present).
3. Flip code25 to manifest prompts (Y-8); the guard is the equality test.
4. Green `tests/run_all.py` + green `--self-test` + valid raw e2e bundle. No moving to QA before that.

## 3. Full review + quality assurance (X-0)

- Independent re-run of every §1 acceptance + Y-INT §2 checklist.
- Frozen/ownership/secrets/tree check (R1 from `REVIEW-X.md`).
- `reports/QA_X_final2.md` report + GO/NO-GO verdict + numbered punch list.
- No push before a written GO.

## 5. Completion plan (executes after Wave-2 GO)

Direct-inspection verified state (not reports): Y-INT integration is
really in the code — `run_suite` converts exceptions to VOID
(`_void_attempt` + `classify_cause`), verifies the frozen pack, seals
bundles (`refuse_overwrite` + `seal_bundle`), passes `scope` with hidden
refusal before any model call, and records `claim_tier` +
`reasoning_conditions`; the CLI carries `--hidden-ok` + sampling flags.
The four SPEC amendments (§14/§27/§28/§B28/§32) are documented, not yet
implemented.

| Phase | Items | Details |
|---|---|---|
| **C1. Wave-2 closure (verify, don't build)** | 1. Green `tests/run_all.py` + `--self-test` confirmed by running | any failure = fix before proceeding |
| | 2. Sealed e2e bundle: one stub run + `verify_bundle_seal == ok`, then delete the bundle | physical proof of integration soundness |
| | 3. Live gate behavior: hidden without `--hidden-ok` = clean REFUSED; security works via the new path | prevents silent Y-4/Y-7 regression |
| | 4. `reports/QA_X_final2.md` report + GO/NO-GO verdict | no push before written GO |
| **C2. Pre-public cleanup** | 1. Delete `__pycache__` + `.DS_Store` | raw tree for users |
| | 2. Current `results/raw/*.json` files **stay** (you work on them) — excluded from commit via `.gitignore`, not deleted | your private results never push public |
| | 3. Confirm `.gitignore` covers `results/raw/RUN-*` and trial bundles | |
| **C3. Fine-Tuning (only after GO, binding order)** | P0 Scaffold: L0/L1/L2 layers in agent-loop + `scaffold_level(s)` + four Gain numbers + golden tests | SPEC §27 |
| | P1 Hardware: hardware object + `device_class` + Tier A/B split + mixed-comparison labeling | SPEC §B28 + §32 |
| | P2 Recovery Precision: deterministic `L/A` formula + (rate, precision) pair in report + three-rule tests | SPEC §14 |
| | P3 Gauntlet: `first_missed` + reference anchor (byte-identical oracle) + tests | SPEC §28 |
| **C4. Release** | 1. Selective `git add` (code + spec + tests only) | 2. R2: clean clone reproduces green 3. First real baseline = R3 before any OFFICIAL number |

Rule: no phase starts before the previous one closes with runnable proof, not a report.

## 6. Agent plan for C1 (Wave-2 closure — 3 parallel agents)

C1 is verification, not construction. All three run in parallel with no
mutual dependency.

| Agent | Task | Allowed scope (read/write) | Required proof |
|---|---|---|---|
| Z-1 integration check | Independent re-run: `tests/run_all.py` + `--self-test` + one sealed e2e bundle | write: `reports/QA_X_final2.md` only (GO/NO-GO verdict); read: everything; no code touched | `verify_bundle_seal == ok` then **delete the bundle**; any failure = numbered punch list, no silent fix |
| Z-2 gate check | Live gate behavior: (1) hidden without `--hidden-ok` = clean REFUSED with no bundle and no model call (2) security via the new path with S3–S5 refused without approval (3) normal code25 bundle succeeds and seals | write: gates section inside `reports/QA_X_final2.md` only; read: `shared/run*.py` + both executors | three CLI commands with verbatim results in the report |
| Z-3 tree audit | Full R1: frozen (pack/template/report.py:86/fixtures) + ownership + secrets scan + tree (no RUN dirs, no `__pycache__`, no `.DS_Store` after cleanup) | write: R1 section inside `reports/QA_X_final2.md` only; read: everything | PASS/FAIL/OPEN table with `file:line` evidence per item |

Closure rule: GO requires Z-1, Z-2, and Z-3 green together in one report.
Any NO-GO goes to the file-owning fix agent (Y-1..Y-9 or Y-INT) — Z agents
never fix; investigator/executor separation is mandatory.

## 7. Agent plan for C3 (Fine-Tuning — 4 sequential agents)

Binding order: P0 ← P1 ← P2 ← P3. No parallelism here — each agent builds
on its predecessor's merged output. Acceptance straight from SPEC
(§14/§27/§28/§B28/§32).

| Agent | Task | Exclusively owned files | Acceptance |
|---|---|---|---|
| F-0 tiers | P0 Scaffold: L0 (chat only) and L1 (read+run only) modes in `episode.py` via allowed-tools key (frozen prompts byte-identical) + `scaffold_level` per attempt + `scaffold_levels` in manifest (via existing `extra=`) + SG, SG_L1 and both relatives in `report_v2` | `suites/agent-loop/episode.py` (mode appends) + `shared/report_v2.py` (SG section) + `tests/backends/test_scaffold_tiers.py` | L0/L1/L2 work; cross-harness = NON_COMPARABLE; four-number goldens |
| F-1 hardware | P1 Hardware: `hardware` object in `collect_environment` (unknown-tolerant) + `device_class` in manifest + Tier A/B split in `report_v2` (current EfficiencyScore number = Tier A; Tier B raw rates + class) + mixed CONDITIONALLY_COMPARABLE label | `shared/runner.py` (environment only) + `shared/report_v2.py` (efficiency section) + `tests/harness/test_hardware.py` | M1 vs i9 labeled not merged; blended number rejected by test |
| F-2 precision | P2 Recovery Precision: deterministic `recovery_precision()` in `scoring.py` (three rules + blind-repeat exclusion + zero NA) + (rate, precision) pair and reading guide in `report_v2` | `shared/scoring.py` (one function) + `shared/report_v2.py` (display lines) + `tests/scoring/test_recovery_precision.py` | thrashing agent: high rate + low precision (golden) |
| F-3 diagnosis | P3 Gauntlet: causal-order `first_missed` + reference anchor (recovery/robustness) in report section — **byte-identical oracle** (B58 hashes unchanged) | `shared/report_v2.py` (gauntlet section) + `tests/scoring/test_gauntlet_diag.py` | hashes identical before/after; ordering + anchor goldens |

Shared F rules: stdlib only; English code; docstring cites a SPEC
section; frozen untouched (frozen agent-loop prompts rewritten byte-wise
not paraphrased); full green after each agent before the next.

## 8. Model B plan — skill inside the agent (an interface to invoke, not a target to test)

The fundamental difference from adapters (`adapters/` = EMO tests an
external agent): here **the user inside their agent** (hermes/codex/
opencode/pi/forge/…) invokes EMO as a skill to test a model. One
portable skill, no adapter per agent.

| Layer | File | Serves | Content |
|---|---|---|---|
| B1 portable skill | `SKILL.md` (repo root, Agent Skills format: frontmatter `name/description` + instructions + commands) | opencode, pi, forge, codex CLI (all read Claude-compatible skill format and run shell) | when to invoke the skill + verbatim `python3 <emo-x>/shared/run.py --suite …` + raw bundle reading + NON-COMPARABLE warning on harness mismatch |
| B2 `/emo` command | `commands/emo.md` | codex (`~/.codex/commands/`) + opencode (custom commands) — same file, no fork | thin wrapper passing (`--suite`, `--trials`, `--seed`) to B1 |
| B3 MCP server | `mcp-server/` (stdio + JSON-RPC: `run_suite`, `self_test`, `health` tools) | open-web / AnythingLLM (chat UIs with no shell — the only possible way) | **done**: `mcp-server/server.py` (stdlib only, 5 tools, same fail-closed gates) + `tests/backends/test_mcp_server.py` (12 tests) — serves any MCP-capable agent |

Binding rules:
1. The skill **invokes** `shared/run.py` as a subprocess — never re-implements logic or copies prompts (frozen stays single-sourced).
2. Every skill-routed result carries the host agent harness (agent name + version) and is labeled NON-COMPARABLE against direct `run.py` results (§B58 rule + `ADAPTERS.md` §0 lesson).
3. codex CLI needs a ChatGPT subscription, not an API key — documented as a constraint, not full support. cline/kilo (VS Code extensions with no CLI) stay manual-trace per `ADAPTERS.md` §6.
4. No new adapter per each of the seven agents — the three existing adapters are sufficient reference samples.

Order was B1 ← B2 ← B3 (conditional on demand) — all three layers done.
