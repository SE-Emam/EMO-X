"""ATIF trajectory export + validation (roadmap: Harbor gap).

Converts EMO-X trajectories (agent-loop P4 shape or raw attempt lists)
to the Agent Trajectory Interchange Format subset Harbor tooling
expects: {"agent": {"name": ...}, "steps": [{"step_id": 1, ...}, ...]}.

Validator enforces: sequential step_ids from 1, agent.name required.
Export never invents content: unmapped fields ride in "emox" extras.
Stdlib only.
"""

ATIF_VERSION = "atif-emox-1"


def _steps_from_trajectory(trajectory, agent_name):
    steps = []
    counter = [0]

    def push(kind, payload):
        counter[0] += 1
        step = {"step_id": counter[0], "agent": {"name": agent_name},
                "kind": kind}
        if isinstance(payload, dict):
            step.update(payload)
        else:
            step["value"] = payload
        steps.append(step)

    traj = trajectory or {}
    for plan in traj.get("plan", []):
        push("plan", {"text": str(plan)[:2000]})
    calls = traj.get("tool_calls", [])
    observations = traj.get("observations", [])
    for i, call in enumerate(calls):
        push("tool_call", call if isinstance(call, dict)
             else {"raw": str(call)[:2000]})
        if i < len(observations):
            push("observation", observations[i]
                 if isinstance(observations[i], dict)
                 else {"raw": str(observations[i])[:2000]})
    for failure in traj.get("failures", []):
        push("failure", failure)
    for recovery in traj.get("recoveries", []):
        push("recovery", recovery)
    for verification in traj.get("verification", []):
        push("verification", verification)
    term = traj.get("termination")
    if term is not None:
        push("termination", term)
    return steps


def export_atif(trajectory=None, attempts=None, agent_name="emox-agent",
                run_id=None):
    """Build an ATIF trajectory dict from EMO-X data.

    trajectory: P4 agent-loop trajectory (preferred). attempts: raw
    attempt list fallback (one step per attempt with its status).
    """
    if trajectory:
        steps = _steps_from_trajectory(trajectory, agent_name)
    else:
        steps = []
        for i, attempt in enumerate(list(attempts or []), 1):
            steps.append({
                "step_id": i, "agent": {"name": agent_name},
                "kind": "attempt",
                "emox": {
                    "task_family_id": attempt.get("task_family_id"),
                    "instance_id": attempt.get("instance_id"),
                    "primary_status": attempt.get("primary_status"),
                    "score": attempt.get("score"),
                },
            })
    doc = {"atif_version": ATIF_VERSION, "agent": {"name": agent_name},
           "steps": steps,
           "emox": {"run_id": run_id,
                    "n_steps": len(steps)}}
    return doc


def validate_atif(doc):
    """Validate ATIF shape. Returns (ok, [reasons]).

    Rules: agent.name non-empty; steps non-empty list; step_id values
    exactly 1..N in order; every step carries agent.name.
    """
    reasons = []
    if not isinstance(doc, dict):
        return False, ["not-a-mapping"]
    agent = doc.get("agent") or {}
    if not isinstance(agent.get("name"), str) or not agent["name"].strip():
        reasons.append("agent.name-required")
    steps = doc.get("steps")
    if not isinstance(steps, list) or not steps:
        reasons.append("steps-nonempty-required")
        return False, reasons
    for i, step in enumerate(steps, 1):
        if not isinstance(step, dict) or step.get("step_id") != i:
            reasons.append("step-id-not-sequential-at-%d" % i)
            break
        name = (step.get("agent") or {}).get("name")
        if not isinstance(name, str) or not name.strip():
            reasons.append("step-agent-name-required-at-%d" % i)
            break
    return (len(reasons) == 0, reasons)
