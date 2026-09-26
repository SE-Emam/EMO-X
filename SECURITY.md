# Security Policy — EMO-X

## Scope

EMO-X evaluates **agent safety with fully synthetic fixtures**:
sandboxed, offline, non-deployable, scope-gated (`docs/security-model.md`,
`SPEC.md` §24, `shared/safety.py`).

- All credentials, dumps, phishing pages, and flags in this repo are
  **fabricated for benchmarking** (`FAKE-` / `EMO{SYNTH_…}` markers).
  There are no real targets, no real secrets, no network execution.
- The executor runs untrusted model output in sandbox-only temp dirs
  with forbidden-path checks and timeouts (`shared/sandbox.py`).

## Reporting a vulnerability

Open a GitHub issue titled `[SECURITY]` describing the affected file and
reproduction steps. Do not include secrets or live targets.

## Red lines (evaluators)

No Tor, no real markets/credentials, authorization via scope-gate first;
isolation violations invalidate the run (see `security-bench/SKILL.md`).
