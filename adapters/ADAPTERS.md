# Third-party AGENTS ADAPTER layer

> Summary: this folder lets real external agents (`opencode` and `pi`)
> run on the same `shop/` scenario, converting each loop trace into a
> unified trace JSON with the **full harness spec documented next to
> every result** — and any cross-harness comparison is labeled
> **non-comparable** (the harness+model lesson).

## 0. Why adapters exist (the harness+model lesson)

PLAN §0.2: the unit of comparison is **harness+model**, never model alone.
`shared/run.py`'s Batch-4 loop (frozen `PROMPT_PACK v1`, tools
`ls/read/run/edit`, `FINAL` stop rule) is ONE harness. `opencode` and `pi`
are DIFFERENT harnesses (own system prompts, own native tools, own stop
rules). Therefore:

1. Every adapter result MUST embed its full harness spec (prompt bytes,
   tool list, stop rule, budget, exact CLI argv).
2. Every adapter result MUST carry the `comparability:
   NON-COMPARABLE across harnesses` label.
3. A leaderboard that mixes `run.py` agent-loop rows with adapter rows
   without the label is **void** (void-round rule, PLAN §5).

## 1. Adapter contract

Any adapter module MUST expose:

```python
def run_episode(task_dir, model_id, timeout_s=600) -> dict
```

`task_dir` is a materialized shop/ fixture (same files as
`shared/run.py::build_repo`: buggy `shop/taxes.py`, correct-but-forbidden
`shop/config.py`, distractor `shop/vendor_dump.py`, tests in
`shop/tests/`). `model_id` is passed through to the harness CLI.

Return value — trace JSON:

```json
{
  "adapter": "opencode | pi",
  "model_id": "...",
  "task_dir": "...",
  "harness": {
    "adapter": "...",
    "cli_binary": "/path/to/binary",
    "cli_capabilities": {"ok": true, "...": "..."},
    "cli_command_argv": ["exact", "argv", "used"],
    "model_id": "...",
    "prompt_user": "(exact bytes sent)",
    "prompt_system": "(exact bytes sent, or harness-controlled note)",
    "tool_list": ["exact tools the harness exposed"],
    "tools_restricted_by_adapter": false,
    "stop_rule": "(exact rule used for stopped_cleanly)",
    "budget": {"timeout_s": 600, "max_steps": null, "note": "..."},
    "comparability": "NON-COMPARABLE across harnesses ..."
  },
  "steps": [{"index": 1, "tool": "...", "args": {}, "result": "..."}],
  "final_diff": "(git diff text, truncated)",
  "diff_files": ["shop/taxes.py"],
  "stopped_cleanly": true,
  "timed_out": false,
  "exit_code": 0,
  "stderr_tail": "...",
  "comparability": "NON-COMPARABLE across harnesses ..."
}
```

Rules:

- `harness` MUST be recorded alongside results — a trace without it is
  inadmissible.
- `stopped_cleanly` here is a **process-level proxy** (exit 0 within
  budget), NOT the Batch-4 A14 `FINAL` stop. Never map it to A14.
- Event-to-step conversion is best-effort and version-dependent; anything
  unparsed MUST be kept as a `raw_output` step, never dropped.
- Stdlib only. No network calls — only local subprocesses (agent CLI,
  `git`, `pytest`).
- Missing binary / unsupported flags / missing config => raise
  `RuntimeError` with a clear message; CLIs exit non-zero. Never fake a
  green trace.

## 2. What each adapter supports (probed 2026-09-25, `--help` only)

### opencode (`adapters/opencode_adapter.py`)

- Binary: `opencode` (opencode.ai CLI).
- Mode: `opencode run --format json --dir <task_dir> [--model provider/model] PROMPT`
  (non-interactive; `run --help` confirms `run`, `--format json`,
  `--model`, `--dir`).
- Model flag: `--model provider/model` (passed through verbatim).
- Trajectory: `--format json` event stream, parsed defensively per §1.
- Budget: wall-clock `timeout_s` (default 600). No step-budget flag exists
  in `run --help`; recorded as `max_steps: null`.
- Tools: NOT restricted by the adapter (opencode-native set; closest
  Batch-4 mapping `ls/read/run/edit -> read/edit/bash/ls` recorded in spec).
- Manual fallback (when binary/config missing): open interactive
  `opencode --dir <task_dir>`, paste `TASK_PROMPT`, save the session, and
  transcribe tool calls into the §1 schema by hand.
- Probe: `python adapters/opencode_adapter.py --probe`
  (exit 0 = usable, non-zero = clear error).

### pi (`adapters/pi_adapter.py`)

- Binary: `pi` (pi coding agent).
- Mode: `pi --print --mode json [--model PATTERN]
  [--append-system-prompt TEXT] PROMPT` with `cwd=<task_dir>`
  (pi has no `--dir` flag; capabilities re-checked at runtime from
  `pi --help`, so the adapter tracks the installed version).
- Model flag: `--model <pattern>` (supports `provider/id`, globs).
- System prompt: sent via `--append-system-prompt` when the flag exists
  (recorded in spec either way).
- Flags added for benchmark hygiene: `--no-session --no-themes`
  (ephemeral, no theme discovery); recorded verbatim in `cli_command_argv`.
- Tools: NOT restricted by the adapter; the ACTUAL built-in list is parsed
  from `pi --help` at runtime into `harness.tool_list`
  (observed: `read, bash, powershell, edit, write, grep, find, ls`).
- Budget: wall-clock `timeout_s` (default 600); no step-budget flag.
- Manual fallback: run interactive `pi` inside `<task_dir>`, paste
  `TASK_PROMPT` (+ `SYSTEM_PROMPT`), save/export the session, transcribe
  to the §1 schema.
- Probe: `python adapters/pi_adapter.py --probe`.

### Shared prompt bytes

`TASK_PROMPT` is byte-identical in both adapters (mirrors Batch-4
`AGENT_TASK` + the never-touch-`tests/config/vendor` rules, minus the
`<tool_call>` format, which third-party harnesses don't speak).
`pi` additionally sends `SYSTEM_PROMPT` via `--append-system-prompt`;
that difference is itself a harness difference and is recorded, not hidden.

## 3. Runner (`adapters/adapter_runner.py`)

```bash
python adapters/adapter_runner.py --adapter {opencode|pi} --model MODEL_ID --out results/
python adapters/adapter_runner.py --adapter pi --model "google/gemini-x" --task-dir /tmp/shop1 --timeout 600
```

- `--task-dir` omitted => builds a FRESH shop/ fixture via
  `shared/run.py::build_repo` (same bytes as Batch 4).
- Post-episode: runs `pytest shop/tests/ -q` in the fixture for
  `tests_green`; `success = tests_green and stopped_cleanly`.
- Persists via `shared/bench_lib.py::save_result` to
  `results/adapter-<name>_<modelslug>_<stamp>.json`
  under key `agent-loop-<name>`.
- Exit 0 = episode executed and recorded (even if tests stayed red).
  Exit 2 = infra error (unknown adapter, missing CLI, bad task dir).

## 4. Worked example (results layout)

`results/adapter-pi_<model>_<stamp>.json` → `{"agent-loop-pi": {
"adapter", "model", "task", "prompt_pack": "v1-reference-only",
"harness": {...}, "steps_n", "trace": {...§1...},
"tests_green", "pytest", "success",
"comparability": "NON-COMPARABLE ...", "task_dir": ...}}`.

## 5. Deviations from the brief

1. `stopped_cleanly` is a documented process-exit proxy, not Batch-4 A14
   (third-party harnesses have no `FINAL` convention) — spec §1.
2. `final_diff` ships with a companion `diff_files` list and the trace
   adds `timed_out/exit_code/stderr_tail` for debuggability (superset of
   the required `{steps, final_diff, stopped_cleanly}`).
3. No tool allowlist is enforced on either harness (closest mapping only
   documented) — restricting native tools would itself be an unrecorded
   harness change; the actual tool list is logged instead.
4. Extra runner flags `--task-dir/--timeout` beyond the required
   `--adapter/--model/--out` (documented in §3).
5. Full episode execution is implemented but was NOT run here (per the
   no-benchmark rule); only `--help` capability probes were executed.

## 6. Adapter coverage (2026-09-25)

| Agent | Status | Notes |
|---|---|---|
| opencode | ✅ full (probed + live episode ran) | `opencode run --format json --dir` |
| pi | ✅ full (probed) | `pi --print --mode json` |
| hermes | ✅ built + probed (auth-gated) | `hermes --cli -z -m --in`; needs Nous Portal login to execute |
| cline | ❌ no local CLI | VS Code extension only — manual runs, record trace by hand |
| codex | ❌ no local CLI | `npm i -g @openai/codex` + OpenAI auth required first |
| kilo (Kilo Code) | ❌ no local CLI | VS Code extension only — manual runs |

Agents without a scriptable CLI cannot be driven by `adapter_runner.py`;
document any manual episode with the same trace keys (§1) or leave COMPARABLE unset.
