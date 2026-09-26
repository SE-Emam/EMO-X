# Task DSL

Contract refs: SPEC sections 6 (task family model), 7 (Task DSL manifest).

## Model

Every semantic task is a family with five layers (SPEC 6): Task
Definition -> Instance Generator -> Environment -> Oracle -> Scoring
Policy. A task must never encode the expected answer into the prompt
generator.

## Manifest fields (SPEC 7)

Required: `id, version, name, category, capabilities, generator,
difficulty, execution, oracle, scoring, variants, timeouts, network,
filesystem`. Validated by `shared/schemas.py::validate_task_manifest`
plus deeper checks in `generators/task_dsl.py`. Canonical SHA256 via
`shared/manifests.py::sha256_manifest` (B58 ManifestHash).

## Generators

- `generators/seeds.py`: `seed -> Random` stream (`"{version}:{seed}"`),
  instance ids `{family}-{variant}-{index:05d}`, SPEC 8 instance records
  with `instance_hash`/`oracle_hash`.
- `generators/instance_factory.py`: manifest + seed + variant + index ->
  byte-identical instance on any machine.
- `generators/mutations.py`: canonical -> paraphrase/naming/constraint/
  structural/adversarial/recovery/novel (SPEC 9 levels C/P/S/A/R/N,
  difficulty bumps for SPEC 10). Exactly one primary variant per
  instance (DEN C14).

## Example

See `generators/task_dsl.py::example_h3_manifest` and
`suites/code-bench-25/manifests/H3.json` (SPEC 7 H3 example).
