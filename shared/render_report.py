"""Render an EMO-X raw bundle as a self-contained HTML report.

Reads results/raw/RUN-ID/{manifest,events,responses,environment}.json*
and writes <out>/report.html + report.json: capability-profile bars,
failure fingerprint, Tier-A/B efficiency, 95% CI, claim/condition/gate
table. No network, no dependencies: inline SVG + CSS only.

Usage:
  python3 shared/render_report.py results/raw/RUN-ID/ --out reports/RUN-ID/
  open reports/RUN-ID/report.html
"""

import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    from report_v2 import build_v2_report
except ImportError:
    from shared.report_v2 import build_v2_report


def _load(name, rundir):
    with open(os.path.join(rundir, name), encoding="utf-8") as f:
        if name.endswith(".jsonl"):
            return [json.loads(l) for l in f if l.strip()]
        return json.load(f)


def _bar(label, value, color="#2c7be5"):
    pct = max(0.0, min(1.0, float(value or 0.0))) * 100.0
    lab = html.escape(str(label))
    return (
        '<div class="row"><span class="lab">%s</span>'
        '<svg width="260" height="14" aria-label="%s %.1f%%">'
        '<rect width="260" height="14" rx="3" class="track"/>'
        '<rect width="%.1f" height="14" rx="3" fill="%s"/></svg>'
        '<span class="val">%.1f%%</span></div>' % (
            lab, lab, pct, pct * 2.6, color, pct))


def render(rundir, outdir):
    """Build report.json + report.html from a raw bundle. Returns outdir."""
    manifest = _load("manifest.json", rundir)
    attempts = _load("events.jsonl", rundir)
    responses = _load("responses.jsonl", rundir)
    try:
        environment = _load("environment.json", rundir)
    except (IOError, ValueError):
        environment = {}
    report = build_v2_report(
        attempts, responses, model_id=manifest.get("model"))
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump({"manifest": manifest, "report": report,
                   "environment": environment}, f, ensure_ascii=False,
                  indent=1)
    profile = report.get("capability_profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    fingerprint = report.get("failure_fingerprint") or {}
    if not isinstance(fingerprint, dict):
        fingerprint = {}
    eff = report.get("efficiency") or {}
    if not isinstance(eff, dict):
        eff = {}
    unc = report.get("uncertainty_95") or {}
    if not isinstance(unc, dict):
        unc = {}
    rows = []
    rows.append("<h1>EMO-X report <small>%s</small></h1>" % html.escape(
        str(manifest.get("run_id", "?"))))
    rows.append("<p>model <b>%s</b> · suite <b>%s</b> · backend <b>%s</b> "
                "· eligibility <b>%s</b></p>" % (
                    html.escape(str(manifest.get("model", "?"))),
                    html.escape(str(manifest.get("suite", "?"))),
                    html.escape(str(manifest.get("backend", "?"))),
                    html.escape(str(report.get("eligibility", "?")))))
    rows.append("<h2>Capability profile</h2>")
    for dim in ("correctness", "generalization", "tool_discipline",
                "recovery", "robustness", "safety", "calibration",
                "efficiency", "long_horizon"):
        rows.append(_bar(dim, profile.get(dim)))
    rows.append("<h2>Failure fingerprint</h2>")
    if fingerprint:
        top = sorted(fingerprint.items(), key=lambda kv: -kv[1])[:12]
        scale = max(1, max(v for _, v in top))
        for name, count in top:
            rows.append(_bar(name, count / scale, color="#e5534b"))
    else:
        rows.append("<p>no failures recorded</p>")
    rows.append("<h2>Efficiency</h2>")
    for tier in ("tier_a", "tier_b"):
        block = eff.get(tier)
        if isinstance(block, dict):
            rows.append("<h3>%s</h3>" % html.escape(tier))
            for key in ("tokens_per_solve", "calls_per_solve",
                        "latency_per_solve", "cost_per_solve"):
                if block.get(key) is not None:
                    rows.append("<p>%s: <b>%s</b></p>" % (
                        html.escape(key), html.escape(str(block[key]))))
    rows.append("<h2>Uncertainty (95% CI)</h2>")
    rows.append("<p>low <b>%s</b> · high <b>%s</b> · se <b>%s</b></p>" % (
        html.escape(str(unc.get("low"))), html.escape(str(unc.get("high"))),
        html.escape(str(unc.get("se")))))
    rows.append("<h2>Run conditions &amp; gates</h2><table>")
    for key in ("claim_tier", "reasoning_conditions", "provider_profile",
                "seed", "trials", "prompt_sha256", "harness_sha256"):
        rows.append("<tr><th>%s</th><td>%s</td></tr>" % (
            html.escape(key),
            html.escape(str(manifest.get(key, "—")))))
    rows.append("</table>")
    page = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>EMO-X report</title><style>"
        "body{font-family:system-ui,sans-serif;max-width:760px;margin:2em auto;"
        "padding:0 1em;color:#111}"
        "small{color:#666}.row{display:flex;align-items:center;gap:8px;margin:3px 0}"
        ".lab{width:150px}.val{width:60px;text-align:right}"
        ".track{fill:#eee}table{border-collapse:collapse}"
        "th,td{border:1px solid #ccc;padding:4px 10px;text-align:left}"
        "</style></head><body>%s</body></html>" % "\n".join(rows))
    with open(os.path.join(outdir, "report.html"), "w",
              encoding="utf-8") as f:
        f.write(page)
    return outdir


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    rundir = argv[0].rstrip("/")
    parent = os.path.dirname(os.path.dirname(rundir.rstrip("/")))
    outdir = os.path.join(parent, "reports",
                           os.path.basename(rundir.rstrip("/")))
    if "--out" in argv:
        outdir = argv[argv.index("--out") + 1]
    print("written", render(rundir, outdir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
