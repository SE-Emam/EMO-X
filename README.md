# EMO-X

Execution-based benchmark skills for coding models and coding agents — reusable with **any agent, any time**, against models on Kaggle, Colab, or any commercial LLM provider. Arabic-first docs, English code.

## What it measures (not just pass/fail)

- **code25** — 25 code/tool tests (Python/JS/TS/Rust/SQL/Postgres/Git/Vercel/Supabase/React/HTML, JSON, diffs, math) with **real execution**, incl. Arabic tasks
- **agent-loop** — a real repo-fixing episode (Batch 4: inspect → locate → patch → test → stop) scored on **efficiency**: tool calls, failures, tokens, latency, clean stop
- **security** — refusal calibration, prompt-injection (direct + poisoned data, incl. concealment), sandboxed CTF-mini, tool-abuse, self-written skills, dark-web patterns (sandboxed only)
- **vision** — UI grounding, Arabic-text reading, element counting (needs a multimodal endpoint; skips gracefully otherwise)
- **adapters** — drive third-party agents (opencode, pi, hermes) with harness specs recorded; cross-harness rows labeled NON-COMPARABLE

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

## Methodology in one paragraph

Frozen `PROMPT_PACK` + fixed harness per comparison (harness+model is the unit);
n=3 with mean±SE; model gaps are judged only by paired cluster-bootstrap 95%
intervals (B54) — no fixed point-gap rule; tokens-per-solved-task, latency and
failure taxonomy reported next to pass rates; raw traces retained; void rounds labeled,
never silently merged. Details in `PLAN.md` §0.
