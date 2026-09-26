# EMO-X

![EMO-X banner — Execution · Measurement · Observability](src/emo-x-banner.png)

Execution-based benchmark skills for coding models and coding agents — reusable with **any agent, any time**, against models on Kaggle, Colab, or any commercial LLM provider. Arabic-first docs, English code.

## What it measures (not just pass/fail)

- **code25** — 25 code/tool tests (Python/JS/TS/Rust/SQL/Postgres/Git/Vercel/Supabase/React/HTML, JSON, diffs, math) with **real execution**, incl. Arabic tasks
- **agent-loop** — a real repo-fixing episode (Batch 4: inspect → locate → patch → test → stop) scored on **efficiency**: tool calls, failures, tokens, latency, clean stop
- **security** — refusal calibration, prompt-injection (direct + poisoned data, incl. concealment), sandboxed CTF-mini, tool-abuse, self-written skills, dark-web patterns (sandboxed only)
- **vision** — UI grounding, Arabic-text reading, element counting (needs a multimodal endpoint; skips gracefully otherwise)
- **issues** — GitHub-issue-style repair tasks (IS1–IS15) with visible + held-out hidden tests; PASS needs both green plus FINAL stop
- **realworld** — mini-real repo fixtures (pagination, config keys, sort stability) with full agent trajectories
- **recovery / robustness / calibration / long-horizon / gauntlet** — fault injection, state drift, abstention, chained checkpoints, and compound 9-dimension scenarios
- **adapters** — drive third-party agents (opencode, pi, hermes) with harness specs recorded; cross-harness rows labeled NON-COMPARABLE

## Features

- **Execution, not eyeballing** — every answer runs in a real toolchain; text similarity never counts.
- **Dynamic variants** — canonical / perturbed / novel instances from deterministic seeds (contamination-resistant).
- **Trajectory-aware** — tool calls, recoveries, re-planning, and clean stops are scored, not just final answers.
- **Failure fingerprints** — every failure gets exactly one primary cause, not a bare zero.
- **Statistical honesty** — paired bootstrap 95% intervals, no fixed point-gap rules, no "winner" without an interval.
- **Self-auditing** — the benchmark monitors its own health (saturation, flakiness, contamination) and flags itself.
- **Sealed provenance** — immutable raw bundles with hashes; any harness change invalidates comparability automatically.

## Why use EMO-X

Single-number leaderboards answer one question ("did it pass?") and hide
everything that matters in deployment: cost per solved task, recovery
after failure, safety under attack, calibration under uncertainty, and
whether success generalizes beyond memorized instances. EMO-X exists
because **a model that scores 65% cheaply, safely, and robustly is not
the same system as one that scores 65% expensively and brittlely** —
and that difference is invisible to pass/fail benchmarks.

## Importance and role

EMO-X is not another leaderboard; it is an **evaluation operating
system for AI agents** (SPEC §48–49: dynamic, execution-based,
trajectory-aware, self-auditing, model-agnostic). Its role is
complementary, not competitive: issue benchmarks (e.g. SWE-bench) ask
*whether real problems get solved*; EMO-X asks *how reliably,
efficiently, safely, and robustly they get solved, and whether the
success generalizes*. Use both: one for ecological validity, one for
measurement science. What distinguishes EMO-X is that it also evaluates
itself — a saturated or contaminated task loses ranking weight by rule,
not by committee.

## Quickstart

```bash
git clone <this-repo> emo-x && cd emo-x
python3 shared/run.py --help   # no pip install needed (stdlib only)

# any OpenAI-compatible endpoint (OpenAI, OpenRouter, DeepSeek, Gemini, vLLM, Ollama…)
python3 shared/run.py --backend openai-generic \
  --base-url https://HOST/v1 --model MODEL-ID --api-key "$KEY" \
  --suite code25 --out results/

# fixed client report + QA stamp
python3 shared/run.py --report results/<model>_<stamp>.json --model MODEL-ID
```

See **[INSTALL.md](INSTALL.md)** for full install/run/troubleshooting,
**[PLAN.md](PLAN.md)** for the methodology, and **[REPORT_TEMPLATE.md](REPORT_TEMPLATE.md)**
for the fixed client-report contract.

## Worked example (end to end)

```bash
# 0. Harness check — deterministic, must print RESULT: PASS
python3 shared/run.py --self-test
#   code-extraction  PASS  ok
#   python-executor  PASS  ok
#   ...
#   RESULT: PASS

# 1. Run two models on the same frozen suite
python3 shared/run.py --backend openai-generic --suite code25 \
  --model MODEL-A --trials 3 --out results/
python3 shared/run.py --backend openai-generic --suite code25 \
  --model MODEL-B --trials 3 --out results/

# 2. What lands on disk (never edited afterwards)
results/raw/RUN-code25-<stamp>-<id>/
├── manifest.json      # prompt/harness/backend hashes, sampling, seed
├── events.jsonl       # one schema-valid record per attempt
├── responses.jsonl    # verbatim model outputs
├── environment.json   # toolchain, platform, hardware class
└── seal.json          # tamper-evident seal (D3)

# 3. Compare with intervals, not point gaps
python3 -c "
from shared.report_v2 import compare_models, render_comparison
# ...load the two bundles, then:
print(render_comparison(comp))"
# Difference: +2.1 pp  95% CI [-1.4 pp, +5.8 pp]
# Status: inconclusive — do not rank on this gap.
```

## Numbers (measured, not claimed)

| What | Count | Source |
|---|---|---|
| Test suites | 14 | `suites/*/` |
| Task manifests | 75 | `suites/*/manifests/*.json` |
| Harness + unit tests | 567 (206+51+157+30+123) | `tests/run_all.py`, all green |
| Self-test checks | 14 | `--self-test`, fail-closed |
| Issue-style families | 15 (IS1–IS15) | vs SWE-bench Lite (300) = **5.0%** |

Comparison with SWE-bench (verified 2026 from swebench.com):

| Dimension | SWE-bench | EMO-X |
|---|---|---|
| Task realism | 2,294 real GitHub issues | 15 issue-style + 3 mini-real fixtures (synthetic, documented) |
| Headline metric | % Resolved (one number) | Capability profile (9 dims + fingerprint + CI) |
| Contamination defense | Static set (known exposure) | Dynamic variants + hidden suite + rotating seeds |
| Statistics | Point estimates | Paired bootstrap 95% CI; no fixed gap rules |
| Cost | Docker-heavy | stdlib only, local, minutes |
| Scope | Code repair (+ multilingual/multimodal) | Repair + security + calibration + recovery + vision + long-horizon |

Honest reading: SWE-bench leads on ecological validity and adoption;
EMO-X leads on measurement science and cost. They answer different
questions — use both.

## Roadmap

| Milestone | Content | Status |
|---|---|---|
| v2.0-alpha | Contracts, sandbox, scoring + goldens, DSL, Core-25, taxonomy | Done (this tree) |
| v2.0-beta | Recovery, drift, tool discipline, calibration, health | Done (suites + `health/`) |
| **v2.0.0-rc1** (current) | Gauntlet, long-horizon, adaptive difficulty, scoring conformance | Code done; **no published OFFICIAL baseline yet** |
| v2.0 | First sealed 3-trial OFFICIAL baseline (R3) | Pending baseline |
| Next | 15→30 issue families; vision out of PILOT; first 3-trial public baseline with CI | Planned (`PLAN-X.md` WP12–WP15) |

No model scores are published in this repo: any number without a sealed
`results/raw/RUN-ID/` bundle is inadmissible here.

## Methodology in one paragraph

Frozen `PROMPT_PACK` + fixed harness per comparison (harness+model is the unit);
n=3 with mean±SE; model gaps are judged only by paired cluster-bootstrap 95%
intervals (B54) — no fixed point-gap rule; tokens-per-solved-task, latency and
failure taxonomy reported next to pass rates; raw traces retained; void rounds labeled,
never silently merged. Details in `PLAN.md` §0.
