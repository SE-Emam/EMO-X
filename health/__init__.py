"""EMO-X benchmark-health package (X-5, WP11).

Contract refs: SPEC sections 11-12 (saturation, health score), SPEC
section 38 (contamination defense), DEN C48-C53 + C69-C72.

Coverage map (each rule implemented exactly once, formulas imported
from shared.scoring where they exist — never reinvented):
  saturation.py      C48 (retention), C49 (gap), C71 (<3 ref models => NA),
                     SPEC B49 penalty + SPEC 11 SATURATED policy.
  discrimination.py  C70 (<5 models => NA) + SPEC B50 leave-one-task-out.
  flakiness.py       C69 (D_flaky = valid trials only) + B48/B51.
  contamination.py   SPEC 38 contamination-risk signals built on C48/C49
                     inputs + C50-C53 calibration-eligibility wrappers.

Binding conventions: NA is None; missing eligibility flags default True;
ERROR/VOID never enter a model-performance denominator (DEN C9).
"""

from health.saturation import saturation_snapshot  # noqa: F401
from health.discrimination import discrimination_snapshot  # noqa: F401
from health.flakiness import flakiness_snapshot  # noqa: F401
from health.contamination import contamination_snapshot  # noqa: F401
