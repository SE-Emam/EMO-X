# Agent-framework matrix (beyond opencode/pi/hermes)

Status key: **integrated** (in-tree adapter + probe) · **generic-ready**
(drivable today via `generic_cli_adapter`) · **roadmap** (needs a
dedicated adapter: library-only, no CLI to drive).

Every row below is NON-COMPARABLE across harnesses by rule
(PLAN §0.2: the unit is harness+model, never model alone).

## Integrated (probe-gated, in-tree)

| Framework | Adapter | Drive |
|---|---|---|
| opencode CLI | `adapters/opencode_adapter.py` | `opencode run --model <route>` |
| pi CLI | `adapters/pi_adapter.py` | `pi --print --mode json` |
| hermes skills | `adapters/hermes_adapter.py` | native skills |
| any CLI agent | `adapters/generic_cli_adapter.py` | `--bin` + `--argv-template` |

## Generic-ready today (no new code — configure the generic adapter)

| Framework | Binary / command | Template |
|---|---|---|
| Aider | `aider` | `--message "{prompt}"` (plus repo files) |
| sgpt (ShellGPT) | `sgpt` | `"{prompt}"` |
| CrewAI CLI | `crewai run` / `crewai kickoff` | project-dependent; record exact argv |
| Any OpenAI-CLI shim | wrapper script | `"--prompt" "{prompt}"` |

Example:

```bash
python3 adapters/generic_cli_adapter.py --probe \
  --bin aider --argv-template '--message "{prompt}"'
python3 adapters/generic_cli_adapter.py \
  --bin aider --argv-template '--message "{prompt}"' \
  --model aider-model --task-dir /tmp/shop --timeout 600
```

## Roadmap (library-only: no CLI to drive → needs dedicated adapters)

| Framework | Why not generic-cli | What an adapter needs |
|---|---|---|
| LangGraph | Python library | graph runner embedding the shop loop + trace export |
| AutoGen | Python library | group-chat driver + message-log → steps converter |
| smolagents | Python library | CodeAgent loop + tool-span → steps converter |
| Pydantic AI | Python library | agent.run() wrapper + span capture |
| Jev (decision) | typed API, no text | out of EMO-X scope (see `docs/model-onboarding.md`) |

Rule for contributors: a new adapter MUST implement the
`run_episode` contract in `adapters/ADAPTERS.md`, MUST embed its full
harness spec, MUST fail closed when its binary/library is absent, and
MUST NOT touch `suites/` or `shared/` scoring.
