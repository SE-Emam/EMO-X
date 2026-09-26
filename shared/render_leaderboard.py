"""Multi-model leaderboard: HTML table + SVG chart + pairwise calls.

Reads N sealed raw bundles (one or many models, per user choice) and
writes leaderboard.html + leaderboard.json: ranked table (pass rate +
95% CI + coverage + per-dimension profile), grouped SVG bar chart with
CI whiskers, and pairwise compare_models verdicts
(significant/directional/inconclusive/non-comparable — never "winner").

Ranking rule: sort by pass-rate point estimate, but any two models
whose CIs overlap share a rank band (no false precision). A lone
single number is never displayed without its interval.

Usage:
  python3 shared/render_leaderboard.py results/raw/RUN-A/ results/raw/RUN-B/ --out reports/board/
  open reports/board/leaderboard.html
"""

import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    from report_v2 import build_v2_report, compare_models
except ImportError:
    from shared.report_v2 import build_v2_report, compare_models
try:
    import scoring
except ImportError:
    from shared import scoring

DIMS = ("correctness", "generalization", "tool_discipline", "recovery",
        "robustness", "safety", "calibration", "efficiency",
        "long_horizon")
DIM_COLORS = ("#2c7be5", "#6f42c1", "#28a745", "#e36209", "#d63384",
              "#20c997", "#fd7e14", "#6610f2", "#17a2b8")


def _load_bundle(rundir):
    rundir = rundir.rstrip("/")
    with open(os.path.join(rundir, "manifest.json"),
              encoding="utf-8") as f:
        manifest = json.load(f)
    events, responses = [], []
    for name in ("events.jsonl", "responses.jsonl"):
        path = os.path.join(rundir, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                events if name.startswith("events") else responses
                (events if name.startswith("events") else responses
                 ).extend(json.loads(l) for l in f if l.strip())
    return manifest, events, responses


def _entry(manifest, events, responses):
    report = build_v2_report(
        events, responses, model_id=manifest.get("model"))
    unc = report.get("uncertainty_95") or {}
    if not isinstance(unc, dict):
        unc = {}
    profile = report.get("capability_profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    return {
        "run_id": manifest.get("run_id"),
        "model": manifest.get("model"),
        "suite": manifest.get("suite"),
        "backend": manifest.get("backend"),
        "claim_tier": manifest.get("claim_tier"),
        "pass_rate": scoring.pass_rate(events),
        "ci_low": unc.get("low"),
        "ci_high": unc.get("high"),
        "coverage": report.get("coverage"),
        "eligibility": report.get("eligibility"),
        "profile": {d: profile.get(d) for d in DIMS},
        "fingerprint": report.get("failure_fingerprint") or {},
    }


def rank_band(entries):
    """Assign rank bands: overlapping CIs share a band (no false ranks).

    Sort by pass-rate point estimate desc; a new band starts only when
    an entry's CI is fully below the band leader's CI.
    """
    ordered = sorted(
        entries, key=lambda e: (-(e["pass_rate"] if e["pass_rate"]
                                  is not None else -1),
                                e["model"] or ""))
    band = 0
    leader_lo = leader_hi = None
    for e in ordered:
        lo, hi = e.get("ci_low"), e.get("ci_high")
        if leader_lo is None or lo is None or hi is None:
            e["band"] = band if leader_lo is not None else 0
            if leader_lo is None:
                leader_lo, leader_hi = lo, hi
        elif hi < leader_lo:
            band += 1
            e["band"] = band
            leader_lo, leader_hi = lo, hi
        else:
            e["band"] = band
            leader_lo = min(x for x in (leader_lo, lo)
                            if x is not None)
            leader_hi = max(x for x in (leader_hi, hi)
                            if x is not None)
    return ordered


def pairwise(entries, bundles):
    """compare_models verdicts for every pair (gated by comparability)."""
    out = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, b = entries[i], entries[j]
            ma, ea, _ = bundles[a["run_id"]]
            mb, eb, _ = bundles[b["run_id"]]
            comp = compare_models(ea, eb, a["model"], b["model"],
                                  manifest_a=ma, manifest_b=mb, B=1000)
            out.append({
                "a": a["model"], "b": b["model"],
                "status": comp.get("status"),
                "difference_pp": (None if comp.get("paired_difference")
                                  is None else round(
                                      100 * comp["paired_difference"], 1)),
                "reason": comp.get("comparability_reason"),
            })
    return out


def _chart(entries):
    """Grouped SVG bars: pass rate + CI whiskers per model."""
    n = len(entries)
    w, bar_h, gap = 560, 18, 26
    h = 40 + n * (bar_h + gap)
    parts = ['<svg width="%d" height="%d" role="img">' % (w + 220, h)]
    parts.append('<text x="10" y="22" font-size="14">Pass rate ± 95% CI</text>')
    for i, e in enumerate(entries):
        y = 40 + i * (bar_h + gap)
        rate = e.get("pass_rate") or 0.0
        lo, hi = e.get("ci_low"), e.get("ci_high")
        bw = max(0.0, min(1.0, rate)) * w
        parts.append(
            '<text x="10" y="%d" font-size="12">%s</text>' % (
                y + 14, html.escape(str(e.get("model")))))
        parts.append(
            '<rect x="150" y="%d" width="%.1f" height="%d" rx="3" '
            'fill="#2c7be5"/>' % (y, bw, bar_h))
        if lo is not None and hi is not None:
            x1, x2 = 150 + max(0.0, min(1.0, lo)) * w, \
                150 + max(0.0, min(1.0, hi)) * w
            parts.append(
                '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" '
                'stroke="#111" stroke-width="2"/>' % (
                    x1, y + bar_h / 2, x2, y + bar_h / 2))
        parts.append(
            '<text x="%d" y="%d" font-size="11">%.1f%% band %d</text>' % (
                160 + w, y + 14, 100 * rate, e.get("band", 0)))
    parts.append("</svg>")
    return "\n".join(parts)


def render_board(rundirs, outdir):
    """Build leaderboard.json + leaderboard.html. Returns outdir."""
    bundles, entries = {}, []
    for rundir in rundirs:
        manifest, events, responses = _load_bundle(rundir)
        bundles[manifest.get("run_id")] = (manifest, events, responses)
        entries.append(_entry(manifest, events, responses))
    entries = rank_band(entries)
    pairs = pairwise(entries, bundles)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "leaderboard.json"), "w",
              encoding="utf-8") as f:
        json.dump({"entries": entries, "pairwise": pairs}, f,
                  ensure_ascii=False, indent=1)
    rows = ["<h1>EMO-X leaderboard "
            "<small>%d run%s</small></h1>" % (
                len(entries), "" if len(entries) == 1 else "s")]
    rows.append(_chart(entries))
    rows.append("<h2>Rank table (bands share overlapping CIs)</h2>")
    rows.append("<table><tr><th>band</th><th>model</th><th>suite</th>"
                "<th>pass rate</th><th>95% CI</th><th>coverage</th>"
                "<th>eligibility</th>"
                + "".join("<th>%s</th>" % d[:8] for d in DIMS)
                + "</tr>")
    for e in entries:
        cells = [e.get("band"), e.get("model"), e.get("suite")]
        rate = e.get("pass_rate")
        cells.append("—" if rate is None else "%.1f%%" % (100 * rate,))
        if e.get("ci_low") is None:
            cells.append("NA")
        else:
            cells.append("[%.1f%%, %.1f%%]" % (
                100 * e["ci_low"], 100 * e["ci_high"]))
        cells.append(e.get("coverage"))
        cells.append(e.get("eligibility"))
        for d in DIMS:
            v = (e.get("profile") or {}).get(d)
            cells.append("—" if v is None else "%.0f" % (100 * v,))
        rows.append("<tr>" + "".join(
            "<td>%s</td>" % html.escape(str(c)) for c in cells) + "</tr>")
    rows.append("</table>")
    rows.append("<h2>Pairwise calls (never “winner”)</h2><table>")
    rows.append("<tr><th>A</th><th>B</th><th>Δ pp</th><th>status</th>"
                "<th>reason</th></tr>")
    for p in pairs:
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td><b>%s</b>"
                    "</td><td>%s</td></tr>" % tuple(
                        html.escape(str(p[k])) for k in
                        ("a", "b", "difference_pp", "status", "reason")))
    rows.append("</table>")
    page = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>EMO-X leaderboard</title><style>"
        "body{font-family:system-ui,sans-serif;max-width:1100px;"
        "margin:2em auto;padding:0 1em;color:#111}"
        "small{color:#666}table{border-collapse:collapse;margin:1em 0}"
        "th,td{border:1px solid #ccc;padding:4px 10px;text-align:left;"
        "font-size:13px}</style></head><body>%s</body></html>"
        % "\n".join(rows))
    with open(os.path.join(outdir, "leaderboard.html"), "w",
              encoding="utf-8") as f:
        f.write(page)
    return outdir


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    rundirs = []
    outdir = "reports/board/"
    skip_next = False
    for tok in argv:
        if skip_next:
            skip_next = False
            continue
        if tok == "--out":
            skip_next = True
            continue
        if tok.startswith("--"):
            continue
        rundirs.append(tok)
    if "--out" in argv:
        outdir = argv[argv.index("--out") + 1]
    if not rundirs:
        print("need ≥1 raw bundle dir", file=sys.stderr)
        return 2
    print("written", render_board(rundirs, outdir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
