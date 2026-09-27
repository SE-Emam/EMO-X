# Community baselines — be the first

No official baseline exists yet. Yours can be the first row on the board.

## How to submit (rules are enforced by code, not trust)

1. Run any model, **3 trials**, frozen suites, same seed schedule:
    ```bash
    EMOX_ALLOW_LOCAL=1 python3 shared/run.py --backend openai-generic \
      --base-url http://localhost:11434/v1 --model YOUR-MODEL \
      --suite code25 --trials 3 --seed 0 --out results/
    ```
2. Keep the sealed raw bundle untouched: `results/raw/RUN-*/`
   (`manifest.json` + `events.jsonl` + `seal.json` — all three required).
3. Copy the bundle dir into `results/community/<model>-<date>/` and open a PR.
4. CI re-verifies the seal + comparability hashes. Tampered or
   unsealed bundles are rejected automatically.

## What gets ranked

Only **COMPARABLE** runs: identical prompt/harness/manifest hashes
(B58). Different code, different board — the leaderboard gate
(`render_leaderboard.py`) enforces this, so conditional comparisons
are report-only and never ordered.

`results/community/` is the one committed exception to the
results git-ignore: everything else under `results/` stays local.
