# Status Model — EMO-X v2.1

Contract refs: SPEC B2, SPEC 34, SPEC B59; DEN C5–C9.

## 1. The 7 statuses

Every attempt has exactly one `primary_status`:

| Status | Meaning |
|---|---|
| `PASS` | Strict task oracle passed. |
| `PARTIAL` | Partial checkpoints earned, strict gate not met. |
| `FAIL` | Model produced a wrong/otherwise failing answer. |
| `TIMEOUT` | Model consumed the permitted execution window (harness healthy). |
| `INVALID` | Model output violated the task output contract (bad JSON, malformed tool call, schema violation). |
| `ERROR` | Infrastructure failed after the run legitimately started (container/executor crash). |
| `VOID` | Round must not be interpreted as evidence about the model (harness defect, provider outage, prompt tamper). |

## 2. Cause table (`STATUS_CAUSES` in `shared/schemas.py`)

| Cause | Status |
|---|---|
| `harness-bug` | `VOID` |
| `backend-unavailable` | `VOID` |
| `prompt-changed` | `VOID` |
| `infra-crash` | `ERROR` |
| `model-malformed-output` | `FAIL` |
| `model-timeout` | `TIMEOUT` |
| `missing-tool` | `ERROR` |

`classify_cause(cause)` returns the status string and raises `SchemaError`
on any unknown cause. Unknown causes never default to a scored status.

## 3. Scored vs excluded rule (DEN C5/C9)

Scored (model performance denominator):

```text
E_scored = {PASS, PARTIAL, FAIL, TIMEOUT, INVALID}
```

Excluded (never model failures):

```text
E_excluded = {ERROR, VOID}
```

Therefore:

```text
N_attempts = N_scored + N_error + N_void
D_attempt  = #{i: status_i in E_scored}
Coverage   = N_scored / N_attempts
```

`ERROR` feeds infrastructure-reliability metrics; `VOID` feeds
benchmark-health metrics. Neither decreases model performance; both
decrease coverage. An infra-caused timeout is `VOID`, not `TIMEOUT`
(DEN C7).

## 4. Where each status is produced

| Layer | Produces |
|---|---|
| Suite executor (`suites/*/executor.py`) | `PASS`, `PARTIAL`, `FAIL`, `TIMEOUT`, `INVALID` — scored model outcomes from oracles, timeouts, and output-contract checks. `ERROR` on executor/infra crash. |
| Runner (`shared/runner.py`, wired by Y-INT) | Maps unexpected exceptions via `classify_cause` to `ERROR`/`VOID`; raises `VoidRun` for void rounds so they are recorded but excluded from scoring. |
| Comparison / scoring (`shared/scoring.py`, `shared/report_v2.py`) | Consumes only `E_scored` for model metrics; reports `ERROR`/`VOID` counts as coverage/health, never as failures. |

`class VoidRun(Exception)` marks a void round. Y-INT catches it in
`run_suite` and records a `VOID` attempt.

## 5. Prompt-tamper => VOID policy (SPEC B59, DEN C6)

Official baselines require a frozen prompt pack. `verify_prompt_pack(name)`
in `shared/manifests.py` hashes `shared/PROMPT_PACK_v1.md` (or
`prompts/PROMPT_PACK_v2.md`) and compares it to the `prompts/SHA256SUMS`
entry. Any mismatch, missing entry, or missing file raises
`VoidRun("prompt-changed...")`, which the runner records as `VOID`:

- the round stays permanently recorded,
- it is excluded from model performance metrics,
- it is included in benchmark-health metrics,
- a tampered pack can never silently become model `FAIL`.
