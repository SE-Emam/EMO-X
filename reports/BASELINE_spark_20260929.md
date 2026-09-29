# OFFICIAL BASELINE (partial): muse-spark-1.3, code25 — 2026-09-29

## Status: CODE25 R3-COMPLETE · OVERALL NOT RANKABLE (CSVRate pending)

This is an honest partial baseline: the code25 legs meet every R3
condition; overall eligibility stays NOT RANKABLE until a clean
security run attaches CSVRate=0. Publishing the partial state with
its gaps is more scientific than waiting silently.

## Conditions (identical both legs)

- Suite: code25 (25 families, canonical+perturbed+novel variants)
- Trials: 3 · Seed: 0 · backend: cli (opencode CLI subprocess, no shell)
- Model: muse-spark-1.3-contributor · Routes: opencode-zen vs kiosapi
- Bundles: `results/community/baseline-spark-{zen,kio}-20260929/`
  (manifest.json + events.jsonl + seal.json, immutable)

## R3 checklist per leg

| Check | zen | kio |
|---|---|---|
| trials == 3 | PASS | PASS |
| seed == 0 | PASS | PASS |
| manifest SPEC-32 | PASS | PASS |
| seal valid | PASS (True, ok) | PASS (True, ok) |
| coverage ≥ 0.95 | PASS (1.000) | PASS (1.000) |
| CSVRate == 0 | **PENDING** (security VOID: rate limits, S3–S5 ungated) | **PENDING** (same) |

## Results (code25, sealed)

| Leg | Pass | 95% CI (cluster) | Wilson 95% |
|---|---|---|---|
| zen (opencode) | **86.4%** (70/81) | [72.0%, 97.3%] | [77.3%, 92.2%] |
| kio (kiosapi) | **77.8%** (63/81) | [60.9%, 90.7%] | [67.6%, 85.5%] |

## Comparison (report-only — CONDITIONAL, never ranked)

- Comparability: CONDITIONALLY_COMPARABLE (unverified material
  capability: distinct serving stacks) · pairing: instance-level.
- Difference: **+8.6 pp** 95% CI [+0.0 pp, +19.8 pp] →
  **directional** (sign consistency 0.95), a lean, not a verdict.
- MDE (80% power): **+14.3 pp** — the observed +8.6 pp is BELOW the
  minimum detectable effect. Correct conclusion: **no significant
  provider gap demonstrated**. This is the framework working as
  designed, not a null result to hide.

## Adversity log (why security is pending)

- kiosapi free quota exhausted mid-session (429 FreeUsageLimitError,
  twice, 15 min apart); zen quota degraded during security leg
  (S1/S2 BACKEND_ERROR VOIDs).
- S3–S5 ungated by design (no scope approval requested for this run).
- Retry policy: quotas recover; rerun `security ×3` per route, attach
  `csv_rate`, re-run this checklist — no code25 rerun needed
  (bundles sealed).

## Durations (UTC 2026-09-29)

- zen code25: 20:54:51 → 21:06:19 (~11.5 min, 81 attempts)
- kio code25: 21:07:09 → 21:53:14 (~46 min, 81 attempts)
- Trial runs (DC1): zen 4/4, kio 0 scored (429)

## Reproduce

```bash
python3 shared/run.py --suite code25 --backend cli \
  --base-url /path/to/opencode --model <route> \
  --trials 3 --seed 0 --out results/
```

Replace `<route>` with `opencode/muse-spark-1.3-contributor-free`
or `kiosapi/muse-spark-1.3-contributor`. Same seed + same code =
same instances; hashes must match for comparability.
