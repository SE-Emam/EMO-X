# EMO-X tests — how to run

Do NOT use top-level `unittest discover -s tests`. It fails for two
load-bearing reasons:

1. `ModuleNotFoundError` (e.g. `generators.task_dsl`): test modules import
   top-level packages that require the repo root on `sys.path`.
2. Duplicate basenames: `suites/code-bench-25/cases.py` and
   `suites/security/cases.py` share a basename and collide in
   `sys.modules` inside one process.

## Canonical invocation (X-5 runner, stdlib only)

```bash
python3 tests/run_all.py
python3 tests/run_all.py --suite scoring   # one suite only
```

The runner executes every suite per-directory
(`tests/harness`, `tests/generators`, `tests/scoring`, `tests/golden`,
`tests/backends`) in isolated `sys.path` contexts (separate subprocesses
with `PYTHONPATH=<root>:shared:generators`) and reports a unified
pass/fail table. Exit code is 0 iff every selected suite passes.

No test directory was restructured to achieve this; the runner works
around the layout as-is.
