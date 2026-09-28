# EMO-X — Installation & Running Guide

> For users who want to **try it**. Theory lives in `SPEC.md`;
> reproducibility rules in `REPRODUCIBILITY.md`.

## 1. Requirements

- Python 3.10+ (stdlib only — no pip packages needed for core)
- Optional verifiers (auto-detected, skipped gracefully if missing):
  `node` (JS tests), `rustc` (Rust test), `tsc` (TypeScript test),
  `psql` + local Postgres (R12), `patch` (diff tests)
- For agent-loop: `pytest` + `git`
- For running tests with pytest directly: `pip install "pytest>=7"` (or `pip install -e ".[dev]"`)
- For agent adapters: the agent CLIs (`opencode`, `pi`, `hermes`) + their own auth
- A model endpoint: any OpenAI-compatible `/v1` (OpenAI, OpenRouter,
  DeepSeek, Gemini, local vLLM/Ollama, Kaggle/Colab tunnel)

## 2. Install — two tracks (pick one)

**Track 1 — benchmark users (`pip install emo-x-eval`):**

```bash
pip install emo-x-eval
emo --self-test    # must end: RESULT: PASS
emo --suite code25 --out results/
```

The `emo` entry behaves exactly like `python3 shared/run.py`
(same hero splash on stderr, same `--quiet`, same sealed bundles).

**Track 2 — harness developers (full checkout):**

```bash
git clone https://github.com/SE-Emam/EMO-X.git emo-x
cd emo-x
python3 shared/run.py --help   # must print usage, no errors
```

No `pip install` needed for Track 2. Keys/endpoints are supplied per run (see §4).

## 3. Verify first (2 minutes, no endpoint needed)

```bash
python3 shared/run.py --self-test   # harness check, must end: RESULT: PASS
python3 tests/run_all.py            # full suite, must end: RESULT: PASS (all 5 suites green)
```

If either fails, stop — a broken harness invalidates every later number
(Comparison rule §B58). Open an issue with the failing lines.

## 4. Run: benchmark a model

API keys are passed via **environment**, not flags:

```bash
export OPENAI_BASE_URL="https://YOUR-HOST/v1"
export OPENAI_API_KEY="$KEY"
export OPENAI_MODEL="MODEL-ID"
```

```bash
# 25 code tests (T/R/H) — start here:
python3 shared/run.py --backend openai-generic --suite code25 --out results/

# Local endpoints (loopback/metadata hosts are refused by default — opt in):
EMOX_ALLOW_LOCAL=1 python3 shared/run.py --backend openai-generic \
  --base-url http://localhost:11434/v1 --model qwen3:1.7b \
  --suite code25 --out results/

# Kaggle/Colab tunnel (native math path enabled automatically for H-tests):
python3 shared/run.py --backend kaggle \
  --base-url https://xxx.ngrok-free.dev/v1 --model mymodel \
  --suite all --trials 3 --out results/

# Agent loop (Batch 4 shop/ scenario):
python3 shared/run.py --backend openai-generic --suite agent-loop --max-steps 15

# New adaptive suites (deterministic seeds — same seed = same instances):
python3 shared/run.py --suite dynamic-code --instances 20 --seed 12345
python3 shared/run.py --suite recovery --fault-rate 0.25
python3 shared/run.py --suite gauntlet --model MODEL-ID
python3 shared/run.py --suite profile --trials 3        # full capability profile

# Benchmark health snapshot over existing raw runs:
python3 shared/run.py --health

# Legacy filters still work:
python3 shared/run.py --suite code25 --only T5,R7,H3
python3 shared/run.py --suite security --only S1,S2 --trials 1
python3 vision-bench/run_vision.py --backend openai-generic --list  # needs multimodal endpoint
```

Every run writes an immutable bundle to
`results/raw/RUN-ID/` (`manifest.json`, `events.jsonl`,
`responses.jsonl`, `environment.json`) — never edit it.

> Equal endpoints are not equal backends: `/v1/chat/completions`
> compatibility says nothing about token counting, reasoning, tool calls,
> seed, or stop behavior. Declare your provider explicitly
> (`--provider-profile openai|openrouter|deepseek|vllm|ollama`; default
> `unknown` = conservative) — the capability manifest is recorded per run
> and mixed-API comparisons are labeled, never silently merged.
> See `docs/backend-contract.md`.

## 5. What each suite needs to actually execute

| Suite | Needs live model? | Needs locally? | Notes |
|---|---|---|---|
| code25 | yes (`/v1`) | python3 + optional node/rustc/tsc/psql/patch | start here |
| agent-loop | yes | python3 + pytest + git | A1–A15 trajectory |
| dynamic-code | yes | python3 | `--seed` reproduces instances exactly |
| recovery / robustness | yes | python3 | fault-injection episodes |
| calibration | yes | python3 | solvable/unsolvable/ambiguous |
| long-horizon / gauntlet | yes | python3 | compound scenarios |
| security S1–S5 | yes | python3 only | 100% synthetic fixtures |
| security S3–S5 scope | no (gate) | env approval only | `EMOX_SCOPE_APPROVED=1` + `EMOX_SCOPE_TARGET=synthetic:...` (or `fixture:`/`offline:`) required — without it S3–S5 are SAFETY-SKIP (fail-closed, `pass: false`), S1/S2 still run |
| vision V1–V5 | yes, **multimodal** endpoint | python3 | skips gracefully on text-only endpoints |
| computer-use C1–C3 | yes | spec-only runner (manual for now) | PILOT |
| adapters | local agent CLI + its auth | task runs locally | labeled NON-COMPARABLE by design |

## 6. Run: benchmark a third-party agent harness

```bash
python3 adapters/adapter_runner.py --adapter opencode --model "provider/model" --timeout 1200
python3 adapters/adapter_runner.py --adapter pi --model "pattern" --timeout 1200
python3 adapters/adapter_runner.py --adapter hermes --model "provider/model" --timeout 1200
```

Results are labeled `NON-COMPARABLE` — same model on two harnesses is
two different systems (harness+model is the unit).

## 6b. Use EMO-X from inside your agent (Model B skill)

One portable skill — no per-agent adapter needed
(opencode, pi, forge, codex CLI, hermes-agent):

- The agent reads [`SKILL.md`](SKILL.md) and runs `shared/run.py` as a
  subprocess; results are tagged with the host agent name + version as
  NON-COMPARABLE against direct `run.py` rows. Per-agent install table
  (incl. hermes repo-local `./.hermes/skills/emo-x/` + `skills trust`,
  `--skills` preload, `skills publish`/`sync`) is in `SKILL.md` itself.
- Slash command: copy [`commands/emo.md`](commands/emo.md) to
  `~/.codex/commands/emo.md` (codex) or the opencode custom-commands
  dir, then `/emo code25`, `/emo profile --trials 3`, …
- Chat-only UIs (open-web / AnythingLLM, no shell): use the MCP
  server — `python3 mcp-server/server.py` (stdio JSON-RPC; any
  MCP-capable agent: opencode, pi, forge, codex, hermes-agent,
  open-web, AnythingLLM, …). Tools: `self_test`, `health`,
  `run_suite`, `run_profile`, `compare_models`. Same fail-closed
  gates (hidden scope, safety scope); credentials never echoed.
  Smoke: `python3 mcp-server/server.py --smoke`.

## 7. Reports

```bash
# v1 fixed client report (frozen template + QA stamp):
python3 shared/run.py --report results/<model>_<stamp>.json --model MODEL-ID
# -> reports/<model>_<stamp>_REPORT.md  +  QA stamp: PASS | FLAGGED:<checks>
```

A FLAGGED report (e.g. missing human review of H3/T5) must not be
presented as final. `REPORT_TEMPLATE.md` documents the 8 mandatory sections.

Capability-profile reports (v2: profile + fingerprint + efficiency +
uncertainty, never one number) are built with `shared/report_v2.py`
over a `results/raw/RUN-ID/` bundle.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `404` streak mid-run | tunnel/model down — restart endpoint, discard the round (void-round rule) |
| Empty `content` on math tests | thinking swallowed output — kaggle backend handles H-tests natively |
| `SKIP ... unsupported-image-call` (vision) | endpoint is text-only — expected, not a failure |
| `FLAGGED:human-review gates` | set `human_reviewed` after manual review of H3/T5 samples |
| adapter `exit 2` | missing CLI/auth (see probe output) — install or log in first |
| `--self-test` FAILs | do not run benchmarks — fix harness first, then re-run |
| `NOT RANKABLE` in a v2 report | check `gate_details`: `CSVRate≠0`, coverage < 95%, or health < 0.80 |
| `ModuleNotFoundError` running pytest directly | use `python3 tests/run_all.py` (see `tests/README.md`) |
