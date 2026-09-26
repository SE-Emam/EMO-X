"""Executor for suites/agent-loop (AG shop + AG2 ledger), runner path.

Thin runner adapter over episode.py (review P0-7/P1-10, one contract):
run_family maps each family to its scenario and returns schema-valid
raw attempts + P4 trajectory responses. The legacy shared/run.py
agent-loop path is untouched.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
for _p in (HERE, SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from shared.manifests import sha256_bytes
except ImportError:
    from manifests import sha256_bytes

SUITE = "agent-loop"
FAMILY_IDS = ("AG", "AG2")
VARIANTS = ("canonical",)


def _load_episode():
    name = "emox_agent_episode"
    if name in sys.modules:
        return sys.modules[name]
    path = os.path.join(HERE, "episode.py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_EP = None


def _ep():
    global _EP
    if _EP is None:
        _EP = _load_episode()
    return _EP


def load_manifest(family):
    """Load the frozen Task DSL manifest for AG/AG2."""
    import json
    fam = str(family or "").strip().upper()
    if fam not in FAMILY_IDS:
        raise KeyError("unknown agent-loop family: %r" % (family,))
    path = os.path.join(HERE, "manifests", "%s.json" % fam)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_family(family, chat, run_id, model_id, trial_id=1, index=1,
               seed=0, variant="canonical", scope=None, scaffold=None,
               max_steps=None):
    """Run one agent-loop episode; returns (attempt, response)."""
    ep = _ep()
    fam = str(family or "").strip().upper()
    if fam not in FAMILY_IDS:
        raise KeyError("unknown agent-loop family: %r" % (family,))
    v = variant or "canonical"
    if v != "canonical":
        raise TypeError("variant %r not supported for family %r"
                        % (variant, family))
    scenario = ep.SCENARIO_FAMILIES[fam]
    result, trajectory = ep.run_episode(
        chat, max_steps=max_steps,
        scaffold=scaffold or ep.DEFAULT_SCAFFOLD, scenario=scenario)
    attempt = ep.episode_attempt(
        result, run_id, model_id, trial_id=int(trial_id), index=index,
        seed=seed, scenario=scenario)
    response = {"instance_id": attempt["instance_id"], "trial_id": trial_id,
                "scenario": scenario,
                "final": result.get("final"),
                "tool_calls": result.get("tool_calls", 0),
                "failed_calls": result.get("failed_calls", 0),
                "terminal_state": result.get("terminal_state"),
                "usage": {"total_tokens": result.get("total_tokens", 0)},
                "reply": str(result.get("final") or "")}
    return attempt, response


def prompt_pack_sha256():
    """SHA256 over both scenario prompts (B58; new family => new key)."""
    ep = _ep()
    parts = []
    for name in sorted(ep.SCENARIOS):
        parts.append(ep.SCENARIOS[name]["system"])
        parts.append(ep.SCENARIOS[name]["task"])
    return sha256_bytes("\n".join(parts).encode("utf-8"))


def harness_sha256():
    """SHA256 of this executor file's bytes (B58 harness hash input)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
