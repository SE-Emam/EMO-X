# Pull request

## Summary

<!-- One or two sentences: what changes and why. Link any related issue. -->

## Test evidence (required)

- [ ] `python3 tests/run_all.py` → `RESULT: PASS (all 5 test groups green: harness/generators/scoring/golden/backends)`
- [ ] `python3 shared/run.py --self-test` → `RESULT: PASS`
- [ ] `CHANGELOG.md` updated (Unreleased section; SPEC §45 versioning rules)
- [ ] No new top-level dependency (core stays stdlib-only; any exception has a recorded decision)

Paste (or summarize) the evidence:

```
# run_all tail:
# self-test tail:
```

## Scope notes (required where applicable)

- [ ] No prompt text changed (any prompt change = new `PROMPT_PACK` version + full re-baseline, else the round is void)
- [ ] No file under `results/raw/` edited (raw is immutable — fixes mint a new `RUN_ID`)
- [ ] If this changes scoring/oracle/harness behavior, the report impact is described below

## Checklist

- [ ] Contracts first (schema/manifest changes frozen before code, if applicable)
- [ ] Golden tests added/updated for scoring changes (including the `D=0 ⇒ NA` edge row)
- [ ] Docs updated (`SPEC.md` / `DENOMINATORS.md` / suite `SKILL.md`, if behavior changed)
