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
try:
    from seal import require_seal
except ImportError:
    from shared.seal import require_seal

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
    cost = report.get("cost") or {}
    return {
        "run_id": manifest.get("run_id"),
        "model": manifest.get("model"),
        "suite": manifest.get("suite"),
        "backend": manifest.get("backend"),
        "claim_tier": manifest.get("claim_tier"),
        "comparison_key": {
            "prompt_sha256": manifest.get("prompt_sha256"),
            "harness_sha256": manifest.get("harness_sha256"),
            "manifest_sha256": manifest.get("manifest_sha256"),
        },
        "backend_capabilities": manifest.get("backend_capabilities") or {},
        "pass_rate": scoring.pass_rate(events),
        "ci_low": unc.get("low"),
        "ci_high": unc.get("high"),
        "coverage": report.get("coverage"),
        "eligibility": report.get("eligibility"),
        "profile": {d: profile.get(d) for d in DIMS},
        "fingerprint": report.get("failure_fingerprint") or {},
        "tokens_total": cost.get("tokens_total"),
        "tokens_per_solve": cost.get("tokens_per_solve"),
    }


#: Material backend fields for the comparability class (SPEC 36).
_CLASS_CAPS_FIELDS = ("tool_calls", "reasoning_tokens", "seed",
                      "token_usage", "vision", "stop_behavior",
                      "max_tokens")


def _comparability_class(entry):
    """Strict leaderboard-eligibility class (review P1-9).

    Entries share a class only on EXACT B58 hash match plus identical
    material backend capabilities: that is the COMPARABLE verdict. Any
    CONDITIONAL/NON_COMPARABLE pair (hash mismatch, unknown/differing
    caps) lands in different classes and is never banded together.
    Returns None for entries without a B58 key (legacy/test data).
    """
    key = entry.get("comparison_key") or {}
    parts = (key.get("prompt_sha256"), key.get("harness_sha256"),
             key.get("manifest_sha256"))
    if not all(parts):
        return None
    caps = entry.get("backend_capabilities") or {}
    material = tuple(caps.get(f, "unknown") for f in _CLASS_CAPS_FIELDS)
    return (parts, material)


def _assign_bands(pool):
    """Band one mutually-comparable pool (existing CI-overlap rule)."""
    ordered = sorted(
        pool, key=lambda e: (-(e["pass_rate"] if e["pass_rate"]
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


def rank_band(entries):
    """Assign rank bands: overlapping CIs share a band (no false ranks).

    P1-9 gate: bands are assigned ONLY within a strict comparability
    class (exact B58 + material caps). A keyed entry with no COMPARABLE
    peer is report-only (band None, ranked False) — conditional
    comparisons never produce an order. Keyless legacy/test entries keep
    the historical single-pool behavior, flagged via rank_note.
    """
    by_class = {}
    keyless = []
    for e in entries:
        cls = _comparability_class(e)
        if cls is None:
            keyless.append(e)
        else:
            by_class.setdefault(cls, []).append(e)
    out = []
    for pool in by_class.values():
        if len(pool) < 2:
            e = pool[0]
            e["band"] = None
            e["ranked"] = False
            e["rank_note"] = ("report-only: no COMPARABLE peer on this "
                              "board (conditional comparisons are never "
                              "ranked)")
            out.extend(pool)
        else:
            for e in _assign_bands(pool):
                e["ranked"] = True
                e["rank_note"] = None
            out.extend(pool)
    keyless_banded = _assign_bands(keyless)
    for e in keyless_banded:
        e["ranked"] = True
        e["rank_note"] = "legacy pool: entry carries no B58 key"
    out.extend(keyless_banded)
    return sorted(out, key=lambda e: (e.get("band") is None,
                                      e.get("band") or 0,
                                      e.get("model") or ""))


def pairwise(entries, bundles):
    """compare_models verdicts for every pair (gated by comparability)."""
    out = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, b = entries[i], entries[j]
            ma, ea, _ = bundles[a["run_id"]]
            mb, eb, _ = bundles[b["run_id"]]
            comp = compare_models(ea, eb, a["model"], b["model"],
                                  manifest_a=ma, manifest_b=mb, B=scoring.BOOTSTRAP_RESAMPLES)
            out.append({
                "a": a["model"], "b": b["model"],
                "status": comp.get("status"),
                "difference_pp": (None if comp.get("paired_difference")
                                  is None else round(
                                      100 * comp["paired_difference"], 1)),
                "reason": comp.get("comparability_reason"),
            })
    return out


#: Colorblind-safe line palette (Okabe-Ito subset + markers).
LINE_COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#56B4E9",
               "#E69F00", "#000000")
LINE_MARKERS = ("o", "s", "^", "D", "v", "p", "x")


def _model_color(model):
    """Deterministic color index per model name (stable across renders)."""
    import hashlib
    digest = hashlib.sha256(str(model or "").encode()).hexdigest()
    return int(digest[:8], 16) % len(LINE_COLORS)


def _line_chart(entries):
    """SVG line chart: capability profile per model across DIMS.

    One polyline per model (deterministic color + marker + legend with
    the model name); missing dimensions break the line (never invent
    points). Curves from different comparability classes share the
    axes but must NOT be read as ranked — the rank table governs.
    """
    dims = [d for d in DIMS]
    w, h, pad = 640, 300, 46
    parts = ['<svg width="%d" height="%d" role="img">' % (w + 220, h)]
    parts.append('<text x="10" y="22" font-size="14">Capability profile '
                 'by model (lines share axes; only bands rank)</text>')
    for i, d in enumerate(dims):
        x = pad + i * (w - 2 * pad) / max(1, len(dims) - 1)
        parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" '
                     'stroke="#ddd"/>' % (x, 40, x, h - 30))
        parts.append('<text x="%d" y="%d" font-size="9" '
                     'text-anchor="middle">%s</text>'
                     % (x, h - 12, html.escape(d[:10])))
    for grid_v in (0.0, 0.5, 1.0):
        y = (h - 30) - grid_v * (h - 70)
        parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" '
                     'stroke="#eee"/>' % (pad, y, w - pad, y))
        parts.append('<text x="%d" y="%d" font-size="9">%.0f%%</text>'
                     % (pad - 34, y + 3, 100 * grid_v))

    def xy(i, v):
        x = pad + i * (w - 2 * pad) / max(1, len(dims) - 1)
        y = (h - 30) - max(0.0, min(1.0, v)) * (h - 70)
        return x, y

    legend_y = 40
    for e in entries:
        color = LINE_COLORS[_model_color(e.get("model")) % len(LINE_COLORS)]
        marker = LINE_MARKERS[_model_color(e.get("model"))
                              % len(LINE_MARKERS)]
        profile = e.get("profile") or {}
        seg, pts = [], []
        for i, d in enumerate(dims):
            v = profile.get(d)
            if v is None:
                if pts:
                    seg.append(pts)
                    pts = []
                continue
            pts.append(xy(i, v))
        if pts:
            seg.append(pts)
        for pts in seg:
            if len(pts) == 1:
                (x, y), = pts
                parts.append('<circle cx="%.1f" cy="%.1f" r="3.5" '
                             'fill="%s"/>' % (x, y, color))
            else:
                parts.append('<polyline fill="none" stroke="%s" '
                             'stroke-width="2" points="%s"/>'
                             % (color, " ".join("%.1f,%.1f" % p
                                                for p in pts)))
                for (x, y) in pts:
                    if marker == "o":
                        parts.append('<circle cx="%.1f" cy="%.1f" r="3" '
                                     'fill="%s"/>' % (x, y, color))
                    else:
                        parts.append('<rect x="%.1f" y="%.1f" width="6" '
                                     'height="6" fill="%s"/>' % (
                                         x - 3, y - 3, color))
        name = str(e.get("model") or "?")
        ranked = "" if e.get("ranked", True) else " (report-only)"
        parts.append('<text x="%d" y="%d" font-size="11" fill="%s">'
                     '■ %s%s</text>' % (
                         w + 6, legend_y, color, html.escape(name),
                         html.escape(ranked)))
        legend_y += 16
    parts.append("</svg>")
    return "\n".join(parts)


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
        band = e.get("band")
        parts.append(
            '<text x="%d" y="%d" font-size="11">%.1f%% %s</text>' % (
                160 + w, y + 14, 100 * rate,
                ("band %d" % band) if band is not None else "report-only"))
    parts.append("</svg>")
    return "\n".join(parts)


def render_board(rundirs, outdir):
    """Build leaderboard.json + leaderboard.html. Returns outdir."""
    bundles, entries = {}, []
    for rundir in rundirs:
        require_seal(rundir)  # P0-6 fail-closed: unsealed runs excluded.
        manifest, events, responses = _load_bundle(rundir)
        bundles[manifest.get("run_id")] = (manifest, events, responses)
        entries.append(_entry(manifest, events, responses))
    entries = rank_band(entries)
    pairs = pairwise(entries, bundles)
    frontier = scoring.pareto_frontier([
        {"label": e.get("model"), "cost": e.get("tokens_per_solve"),
         "accuracy": e.get("pass_rate"), "cost_unit": "tokens-per-solve"}
        for e in entries])
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "leaderboard.json"), "w",
              encoding="utf-8") as f:
        json.dump({"entries": entries, "pairwise": pairs,
                   "pareto_frontier": frontier}, f,
                  ensure_ascii=False, indent=1)
    rows = ["<h1>EMO-X leaderboard "
            "<small>%d run%s</small></h1>" % (
                len(entries), "" if len(entries) == 1 else "s")]
    rows.append(_chart(entries))
    rows.append(_line_chart(entries))
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
    rows.append("<h2>Cost frontier (tokens-per-solve vs pass rate)</h2>")
    if frontier:
        rows.append("<p>Nondominated runs (HAL cost gap): cheaper is "
                    "better at equal accuracy; entries without token "
                    "accounting are excluded, never zero-filled.</p>"
                    "<table><tr><th>model</th><th>tokens/solve</th>"
                    "<th>pass rate</th></tr>")
        for point in frontier:
            rows.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                html.escape(str(point.get("label"))),
                html.escape(str(point.get("cost"))),
                html.escape(str(point.get("accuracy")))))
        rows.append("</table>")
    else:
        rows.append("<p>No frontier: no entries with both token "
                    "accounting and pass rate.</p>")
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
