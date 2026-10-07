# Security Policy — EMO-X

## Scope

EMO-X evaluates **agent safety with fully synthetic fixtures**:
sandboxed, offline, non-deployable, scope-gated (`docs/security-model.md`,
`SPEC.md` §24, `shared/safety.py`).

- All credentials, dumps, phishing pages, and flags in this repo are
  **fabricated for benchmarking** (`FAKE-` / `EMO{SYNTH_…}` markers).
  The generated-code executor uses Docker with networking disabled,
  a read-only container root, and only a dedicated temporary workspace
  mounted read/write (`shared/sandbox.py`). Each container is limited to
  1 GiB RAM, 2 CPUs, and 128 processes; at most the last 1 MiB of combined
  output is retained. It fails closed if Docker or the
  `emox-sandbox:latest` image is unavailable; build it with
  `make sandbox-image`.
- The Docker daemon and sandbox image are trusted components. This
  boundary does not constrain third-party agent CLIs invoked by optional
  adapters; those tools need their own security review and isolation.

## Reporting a vulnerability

Open a GitHub issue titled `[SECURITY]` describing the affected file and
reproduction steps. Do not include secrets or live targets.

## Red lines (evaluators)

No Tor, no real markets/credentials, authorization via scope-gate first;
isolation violations invalidate the run (see `security-bench/SKILL.md`).
