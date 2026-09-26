# Backend contract

Contract refs: SPEC sections 36 (capability contract), 37 (reasoning
mode), B58 (comparison validity). Code: `shared/backends.py`
(`get_capability_manifest`, `comparability`),
`shared/manifests.py::comparability_with_capabilities`.

## Core rule

`/v1/chat/completions` compatibility is a **path**, not a behavior
contract. It says nothing about token counting, reasoning, tool calling,
streaming, stop behavior, seed, or max-tokens semantics. Equal paths
across providers are therefore **never** assumed equal backends.

## Interface

`shared/backends.py::make_chat(backend, base_url, model, api_key)` ->
`chat(messages, temp, max_tokens, think, num_predict)` returning
`(text, secs, usage)`. Backends: `kaggle | colab | openai-generic`
(stdlib `urllib` only). Offline smoke runs use `--backend stub`
(deterministic canned replies; harness plumbing only, never official).

## Capability manifest (SPEC 36)

Every run records `backend_capabilities` in its manifest
(`shared/runner.py::build_manifest`). Fields and vocabulary:

| Field | Values | Notes |
|---|---|---|
| `chat` | supported / unsupported | transport works |
| `streaming` | supported / unsupported | harness always uses `stream:false` |
| `tool_calls` | native / emulated / unsupported / unknown | provider-side tool use |
| `reasoning_tokens` | supported / unsupported / unknown | |
| `seed` | supported / unsupported / unknown | deterministic sampling |
| `token_usage` | exact / estimated / unknown | `usage` passthrough vs `eval_count` |
| `vision` | supported / unsupported / unknown | image input parts |
| `stop_behavior` | supported / unsupported / unknown | stop sequences honored |
| `max_tokens` | enforced / approximate / unknown | |

Material fields (affect comparability): `tool_calls`,
`reasoning_tokens`, `seed`, `token_usage`, `vision`, `stop_behavior`,
`max_tokens`. Anything unverified is `unknown` — never a permissive guess.

`openai-generic` spans many providers, so it takes a `--provider-profile`
(`unknown` default, conservative | `openai` | `openrouter` | `deepseek` |
`vllm` | `ollama`). Unknown providers fall back to `unknown`.

## Comparability verdicts

| Verdict | Meaning |
|---|---|
| `DIRECT` | B58 hashes match AND all material capabilities equal and known |
| `CONDITIONALLY_COMPARABLE` | hashes match; differences are unknown or immaterial |
| `NON_COMPARABLE` | B58 hash mismatch (always wins) OR a material conflict |

## Reasoning mode (SPEC 37)

Explicit values: `enabled | disabled | provider_default | native`. A
task result must never silently change reasoning mode; the mode is
recorded in the run manifest.
