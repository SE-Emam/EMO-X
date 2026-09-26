---
description: Run the EMO-X benchmark (self-test, suites, profile, health, reports) via shared/run.py or the emo-x MCP tools
---

![EMO-X banner — Execution · Measurement · Observability](../src/emo-x-banner.png)

```text
######  #    #   ####   #    #
#       ##  ##  #    #   #  #
#####   # ## #  #    #    ##
#       #    #  #    #   #  #
######  #    #   ####   #    #
Measure what agents accomplish — not what they say
```

# /emo — run EMO-X from your agent

Thin wrapper over the `emo-x` skill (see `SKILL.md`). Passes arguments
through to `shared/run.py`; adds nothing, invents nothing.

## Usage

```text
/emo code25 [--trials N]
/emo profile [--trials N]
/emo dynamic-code [--instances N] [--seed S]
/emo recovery [--fault-rate F]
/emo gauntlet
/emo health
/emo self-test
/emo report <results-json> --model MODEL-ID
```

## Behavior

1. Resolve `EMOX` to the emo-x repo root (ask once, remember).
2. If the command is not `health`, `self-test`, or `report`, run
   `self-test` first when it has not passed in this session — a broken
   harness voids every later number (SPEC §B58).
3. Execute the matching `SKILL.md` command verbatim with the given flags.
4. Report Capability Profile + failure fingerprint + efficiency +
   uncertainty — never one number (SPEC §B61). Comparisons only via
   `compare_models` (`significant / directional / inconclusive`).
5. Tag every result with the host agent name + version as
   NON-COMPARABLE against direct `run.py` rows.

## Install

- codex: copy this file to `~/.codex/commands/emo.md`
- opencode: copy this file to its custom-commands dir as `emo.md`
