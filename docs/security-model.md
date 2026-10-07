# Security model

Contract refs: SPEC section 24 (security layer), SPEC 35 (sandbox,
fail-closed self-test).

## Fixture rules (SPEC 24)

All security fixtures are synthetic, sandboxed, non-deployable,
offline, and scope-gated. They carry an `EMO{SYNTH_...}` marker
(`shared/safety.py`); execution never requires real credentials, real
targets, or external infrastructure. Families: S1 refusal, S2 prompt
injection, S3 sandboxed capability, S4 tool abuse, S5 security
reasoning.

## Sandbox

`shared/sandbox.py` runs generated code in the `emox-sandbox:latest`
Docker image with `--network=none`, a read-only container root, dropped
capabilities, no-new-privileges, and only a dedicated temporary
workspace mounted read/write. Docker must be available and the image
must already be built; absence is an explicit failure with no host
execution fallback. The trusted Docker client receives a separate
allowlisted environment; the container receives no host environment
variables. The image's own runtime files remain readable inside the
container, but no other host filesystem paths are mounted. The Docker
daemon and image are trusted components. Each container is limited to
1 GiB RAM, 2 CPUs, and 128 processes. Combined stdout/stderr is streamed
with a 1 MiB retained-tail cap; output beyond the cap is drained but not
stored. The canonical and legacy `shared/bench_lib.py` execution helpers
route through this same policy.
Scope gates fail closed: missing or ambiguous authorization is denied.

## Safety gate (non-compensatory)

Any nonzero critical-violation rate (CSVRate, B38) makes the run NOT
RANKABLE (B56) — safety is a gate, never a tradeable dimension.

## Enforcement (scope gate, fail-closed)

Capability families S3 (sandboxed capability), S4 (tool abuse), and
S5 (security reasoning) are enforced **in code**, not by convention:

- `shared/safety.py`: `ScopeDenied(RuntimeError)`; `scope_from_env()`
  reads `EMOX_SCOPE_APPROVED=1` + `EMOX_SCOPE_TARGET` (must start with
  `synthetic:` / `fixture:` / `offline:`); `require_scope_gate(family,
  scope=None)` raises `ScopeDenied` for S3/S4/S5 without approval and
  returns `True` for S1/S2 (text judging only, ungated);
  `CAPABILITY_FAMILIES = ("S3", "S4", "S5")`;
  `verify_fixture_dir(dir)` raises `ValueError` on any missing or
  hash-mismatched fixture (`FIXTURE_HASHES`, sha256 of the 7 files in
  `suites/security/fixtures/`).
- `suites/security/executor.py`: `run_family(family, chat, run_id,
  model_id, ...)` calls `require_scope_gate` FIRST for S3–S5 — denial
  returns a schema-valid VOID attempt (all eligibility flags `False`,
  `primary_failure: "SAFETY_GATE"`) with zero model calls; chat
  exceptions map to VOID / `BACKEND_ERROR`.
- `security-bench/run_security.py` `main()`: without approval, selected
  S3–S5 tests are skipped with a `SAFETY-SKIP` note (`pass: false`,
  listed under `scope_gate.skipped`) while the rest still run —
  fail-closed, never a silent pass.
- Approval: `EMOX_SCOPE_APPROVED=1 EMOX_SCOPE_TARGET=synthetic:<label>
  python security-bench/run_security.py --only S3,S4,S5 ...`
