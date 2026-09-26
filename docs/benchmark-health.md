# Benchmark health

Contract refs: SPEC sections 8 (P8: the benchmark evaluates itself),
11 (saturation), 12 (health score), 38 (contamination defense),
39 (aging); DEN C48-C53, C69-C72.

## Signals (`health/`)

- Saturation (`saturation.py`, C71/B49/SPEC 11): mean pass over the
  reference population; NA when fewer than 3 reference models.
  SATURATED when success stays >0.98 with low variance/discrimination;
  saturated tasks keep historical baselines but lose ranking weight.
- Discrimination (`discrimination.py`, C70/B50): leave-one-task-out
  Pearson; NA when fewer than 5 models, missing scores, or constant
  inputs.
- Flakiness + validity (`flakiness.py`, C69/B48/B51): `4p(1-p)` on
  valid trials only (`D_flaky` excludes ERROR/VOID); validity =
  `1 - infra_failures/attempted`.
- Contamination + calibration eligibility (`contamination.py`, SPEC 38,
  C48-C53): high-canonical/low-retention or hash overlap raises a
  rotation flag (never a model penalty); Brier/ECE run on `D_cal` only
  (valid confidence + resolved outcome).
- Composite: TaskHealth = geometric mean excluding NA components (C72);
  benchmark health = mean over tasks (B53).

## Operations

`python shared/run.py --health` prints the snapshot over stored raw
runs. Per SPEC 39, flagged tasks rotate to new variant families while
history is preserved — benchmark maintenance is continuous.
