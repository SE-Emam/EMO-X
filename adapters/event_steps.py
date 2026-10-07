"""Shared JSONL event normalizer for agent adapters (auditor P1-17).

Single canonical implementation behind opencode/pi adapter event
parsing. The per-adapter `_normalize_events` functions delegate here,
so the two files can no longer drift apart silently.

Best-effort conversion of `<tool>-format json` CLI events to steps.
The JSON event schema is version-dependent, so parse defensively: any
line that decodes to a dict with tool-ish keys becomes a step; anything
else accumulates into a trailing raw-output step (never drop evidence).

Stdlib only. Importable both standalone (`python adapters/x.py`, where
adapters/ is sys.path[0]) and via adapter_runner (adapters/ on path).
"""

import json


def normalize_jsonl_events(stdout, trunc=2000):
    """Normalize JSONL CLI output to [{index, tool, args, result}]."""
    steps = []
    raw = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            raw.append(line)
            continue
        if not isinstance(ev, dict):
            raw.append(line)
            continue
        tool = ev.get("tool") or ev.get("function") or ev.get("name") or ev.get("type") or "event"
        args = ev.get("args") or ev.get("input") or ev.get("params") or {}
        result = ev.get("result") or ev.get("output") or ev.get("text") or ev
        if isinstance(result, (dict, list)):
            result = json.dumps(result, ensure_ascii=False)[:trunc]
        steps.append(
            {
                "tool": str(tool)[:80],
                "args": args if isinstance(args, dict) else {"value": str(args)[:trunc]},
                "result": str(result)[:trunc],
            }
        )
    if raw:
        steps.append({"tool": "raw_output", "args": {}, "result": "\n".join(raw)[-trunc:]})
    if not steps:
        steps.append(
            {
                "tool": "raw_output",
                "args": {},
                "result": (stdout or "")[-trunc:] or "(empty CLI output)",
            }
        )
    for i, s in enumerate(steps, 1):
        s["index"] = i
    return steps
