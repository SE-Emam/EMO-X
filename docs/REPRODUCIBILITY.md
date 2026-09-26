# Reproducibility — run manifest (rebuild source of truth)

Contract refs: SPEC §32 (run manifest), §33 (raw bundle), B58
(comparison validity). Code: `shared/runner.py::build_manifest`,
`shared/runner.py::collect_environment`.

Every official result must be reproducible from its raw bundle alone:

```text
results/raw/RUN-ID/
├── manifest.json      # §32: the 20 fields listed below
├── events.jsonl       # every attempt
├── responses.jsonl    # verbatim model outputs
└── environment.json   # runtime versions, toolchain, platform
```

## Manifest field list (exact — 20 fields)

`shared/runner.py::build_manifest` records exactly these fields
(toolchain/python/platform/arch/git-sha/model_sha256/timestamp
included; CLI sampling flags `--temperature/--top-p/--top-k/--context`
are owned by Y-INT and flow in via `sampling`):

| # | Field | Notes |
|---|---|---|
| 1 | `benchmark_version` | e.g. `2.0.0` |
| 2 | `suite` | suite key (e.g. `code25`) |
| 3 | `prompt_pack` | frozen pack id (`PROMPT_PACK_v1/v2`) |
| 4 | `prompt_sha256` | real pack hash (B58; never stubbed) |
| 5 | `harness_sha256` | real harness hash (B58; never stubbed) |
| 6 | `harness_git_sha` | `git rev-parse HEAD`, or `unknown` |
| 7 | `backend` | e.g. `stub`, `kaggle`, `openai-generic` |
| 8 | `provider_profile` | e.g. `stub`, `unknown`, `openai`, … |
| 9 | `backend_capabilities` | SPEC §36 capability manifest mapping |
| 10 | `model` | model id string |
| 11 | `model_sha256` | `sha256("model:"+model)` — stable per model id |
| 12 | `temperature` | sampling param (default `0.4`) |
| 13 | `top_p` | sampling param (nullable) |
| 14 | `top_k` | sampling param (nullable) |
| 15 | `context` | sampling param (nullable) |
| 16 | `seed` | integer seed |
| 17 | `trials` | trials per instance (positive int) |
| 18 | `run_id` | unique run id (never reused) |
| 19 | `timestamp_utc` | ISO-8601 UTC creation time |
| 20 | `runner_version` | e.g. `2.0.0` |

`environment.json` (`collect_environment()`) records:
`python`, `platform`, `architecture`,
`toolchain{python, node, rustc, tsc, sqlite, postgres}`,
`harness_git_sha`, `written_utc`
(plus `benchmark_version` / `runner_version`).

Covered by `tests/harness/test_rebuild_manifest.py`: every field above
is asserted present on a real `build_manifest` + `collect_environment()`
result; toolchain values are strings; `model_sha256` is stable;
two runs yield different `run_id`s and both validate.

## Rebuild rule

Same `seed` + same manifest + same frozen prompt pack
⇒ identical `prompt_sha256` / `harness_sha256` / `instance_hash` /
`oracle_hash` on any machine. Scoring is a pure function
(`RawLogs + Spec + Config → Scores`); two results are DIRECTLY
comparable only if `prompt_sha256`, `harness_sha256`, and the task
manifest hash all match (§B58).

## Unknown-tolerant policy

Rebuild metadata must never block a run and must never guess.
Any toolchain / version / SHA value that cannot be determined is
recorded as the string `"unknown"` (or `"unknown …"` with a reason,
e.g. `"unknown (binary not found)"`). Collectors never raise and
never emit empty values: every toolchain entry is a non-empty string.
