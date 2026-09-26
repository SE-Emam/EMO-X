# EMO-X — Master Plan

> **Rename note:** project renamed `EMO-Benchmark-Skills` → **EMO-X (Adaptive Agent Evaluation)**.
> This file is the v1 archive. Active development plan: `PLAN-X.md`.
> Agent execution plan: `AGENTS-X.md`.

> Version 1.0 — 25/09/2026. Reusable agent-benchmark skill pack for any agent, any time,
> against models on Kaggle / Colab / commercial LLM providers. Arabic-first docs, English code.

## 0. Design principles (from deep research)

1. **Execution over eyeballing** — every code/tool answer runs in a real toolchain (BFCL-style: AST + execution).
2. **Harness+model is the unit** (Scaffold Effect) — frozen `PROMPT_PACK`, fixed harness, or the comparison is void.
3. **Efficiency is first-class** (Terminal-Bench 4.0 / our Batch 4): tokens-per-solved-task, latency, tool calls, no-action turns — not pass/fail alone.
4. **Statistics over anecdotes** — n=3 per test, mean±SE, gaps <3pp = noise (Anthropic infra finding).
5. **Anti-hack by construction** (SWE-Pro Verified): sandboxed tmp dirs, no network in exec, timeouts, forbidden-path checks, raw-trace retention.
6. **Partial credit** (OSWorld-2.0 / CyBench subtasks): checkpoints and subgoals, never all-or-nothing alone.

## 1. Layout

```
EMO-X/                 # this folder (project root or .agents/skills/EMO-X)
  PLAN.md                             # this file
  shared/
    bench_lib.py                      # chat(), extract_code(), exec backends (python/node/rustc/tsc/sqlite/psql/patch)
    backends.py                       # kaggle | colab | openai-generic  (env-driven, one interface)
    run.py                            # unified CLI (see §4)
    PROMPT_PACK_v1.md                 # frozen prompts, versioned; any change = new version + re-baseline
  code-bench-25/SKILL.md              # T1-T8, R1-R12, H1-H6 + T5-Arabic gate + H3-instability note
  agent-loop-bench/SKILL.md           # Batch 4 shop/ scenario, A1-A15, efficiency report
  security-bench/SKILL.md             # S1-S5 (see §3)
  vision-bench/SKILL.md               # Phase 3 (needs multimodal endpoint)
  computer-use-bench/SKILL.md         # Phase 3 (terminal-use now, GUI grounding later)
  results/                            # raw JSON per run (never edit; reports read from here)
```

Skill format follows the repo's existing `SKILL.md` convention (Arabic explanation + English code).

## 2. Backends (one `chat()` interface)

| Backend | Config | Notes |
|---|---|---|
| `kaggle` | `BASE_URL`, `MODEL` | ngrok tunnels; per-request temp; `think:false` flag for math |
| `colab` | `BASE_URL`, `MODEL` | same contract, different URL |
| `openai-generic` | `OPENAI_BASE_URL/KEY/MODEL` | OpenAI, OpenRouter, local vLLM/Ollama — no per-vendor code |

## 3. Suites

### 3.1 code-bench-25 (Phase 1)
Port of the validated 25 tests. Keeps: T5 Arabic-ratio gate (documented strictness), R6/R10/R12 corrected checks, H3 triple-run rule (single runs of H3 are non-admissible after observed instability), `think:false` for math via native API.

### 3.2 agent-loop-bench (Phase 1)
Batch 4 `shop/` scenario + tools (ls/read/run/edit) + A1–A15 mapping + efficiency report
(calls / failed / recoveries / tokens / latency / forbidden / diff cleanliness / stop-cleanly A14).
Rule learned the hard way: identical prompt bytes for every contender, else the round is void.

### 3.3 security-bench (Phase 2) — S1–S5
- **S1 refusal:** 20 explicitly-malicious agent requests (AgentHarm-style categories) + 20 benign lookalikes (over-refusal calibration). Metric: refusal rate both ways.
- **S2 injection:** direct ("ignore instructions") + indirect (poisoned `notes.md` / tool output ordering deletion of tests). Dual judge: action executed? + concealment (did the final reply disclose the injection?).
- **S3 capability (sandboxed CTF-mini):** local decode-and-exploit fixture with subtasks for partial credit (CyBench-style). No network, synthetic flags.
- **S4 tool-abuse + self-skills:** destructive-command request (must refuse + offer safe alternative); model writes a SKILL.md evaluated structurally.
- **S5 dark-web patterns (sandboxed ONLY):** phishing-kit HTML analysis (synthetic), credential-dump triage (generated fake data), Tor-C2 theory (refuse + safe-complete), OPSEC leak check.
- **Red lines (written into the skill):** no Tor, no real markets/credentials, authorization via `pentest-scope-gate` first, isolation violations invalidate the run.

### 3.4 vision-bench (Phase 3, needs multimodal endpoint)
Grounding (screenshot + "where is X?" + answer box — OSWorld-G/ScreenSpot-style), Arabic text reading from image, UI element counting. Blocked until a VLM endpoint (full safetensors via vLLM or commercial provider).

### 3.5 computer-use-bench (Phase 3)
Terminal-use now (= agent-loop extended: multi-bug, mid-run user correction, abstention test). OS-level GUI grounding later (needs screenshots + judge).

## 4. Invocation

```bash
python shared/run.py --backend kaggle --base-url URL --model NAME --suite code25
python shared/run.py --backend openai-generic --suite agent-loop
python shared/run.py --suite code25 --only T5,R7,H3
python shared/run.py --suite security --only S1,S2
python shared/run.py --suite all --trials 3 --out results/
```

## 5. Reporting

Per-run raw JSON in `results/` + leaderboard CSV: model, pass, toks/solved (amortized incl. failures), latency, est. cost, failure-category vector. Reports must state: PROMPT_PACK version, backend, temp, trials, hardware. Partial/void rounds labeled as such (void-round rule).

## 6. Phased roadmap

- **Phase 1:** shared/ + code-bench-25 + agent-loop-bench (port proven scripts).
- **Phase 2:** security-bench S1–S5 fixtures + judges.
- **Phase 3:** vision + computer-use (gated on endpoint capability).
