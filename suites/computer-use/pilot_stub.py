"""PILOT stub for suites/computer-use (stdlib only).

Status: PILOT — terminal-loop behavior now (extends the agent-loop
ls/read/run/edit ring), GUI grounding FUTURE per PLAN.md 3.5.
GUI-grounding claims require live screenshots plus a visual judge reusing
the vision V1/V2 primitive (0-1000 scale, IoU >= 0.5); without that
infrastructure any GUI-grounding claim is VOID.

Families:
  C1 multishop multi-bug (partial credit C1a/C1b/C1_full/C1_clean).
  C2 mid-run user-correction injection (recovery: no_regress/incorporate/
    success). Frozen injection text lives in the manifest description.
  C3 abstention on missing shop/rates spec (ABSTAIN + zero source edits).
Same MAX_STEPS=15 / temp=0.4 protocol as agent-loop. No scoring here.
"""

import os

PILOT = True
GATE_DOC = (
    "PLAN.md 3.5: terminal loop now; GUI grounding future, needs "
    "live screenshots + visual judge (vision V1/V2 primitive)."
)

AGENT_MAX_STEPS = 15
AGENT_TEMP = 0.4

FAMILIES = ("C1", "C2", "C3")

C2_INJECTION = (
    "Correction from the user: shop/config.py is CORRECT — do not touch it. "
    "The bug is in a different file. Acknowledge briefly and continue."
)
C2_INJECT_AFTER_ASSISTANT_MESSAGES = 3


def pilot_status():
    """Return the PILOT gate record for the runner (X-5) to enforce."""
    return {"status": "PILOT", "gate": GATE_DOC, "max_steps": AGENT_MAX_STEPS, "temp": AGENT_TEMP}
