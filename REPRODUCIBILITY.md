# Reproducibility — EMO-X

Every official result must be reproducible from its raw bundle alone:

```text
results/raw/RUN-ID/
├── manifest.json      # SPEC §32: benchmark/prompt/harness versions + hashes,
│                      # model, backend, sampling params, seeds, trials, hardware
├── events.jsonl       # every attempt (DEN §C83 fields + §C4 identity)
├── responses.jsonl    # verbatim model outputs
└── environment.json   # runtime versions, sandbox specs
```

## Rules

1. Same `seed` + same manifest + same frozen prompt pack → byte-identical
   `instance_hash` / `oracle_hash` on any machine (`generators/seeds.py`).
2. Scoring is a pure function: `RawLogs + Spec + Config → Scores`
   (`DENOMINATORS.md` §C84). No model-name or leaderboard peeking.
3. Two results are DIRECTLY comparable only if `PromptHash`,
   `HarnessHash`, and `TaskManifestHash` all match (§B58).
4. `ERROR`/`VOID` never become model failures; coverage < 95% ⇒ PILOT,
   not OFFICIAL BASELINE (§B59).
5. Uncertainty: cluster bootstrap over task families, 95% CI (§B54).

## Verify a run

```bash
python3 shared/run.py --self-test   # harness healthy?
python3 tests/run_all.py            # 5/5 suites green?
# recompute any derived metric from results/raw/RUN-ID/ with shared/scoring.py
```
