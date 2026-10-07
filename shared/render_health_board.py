"""Benchmark-health dashboard: HTML board from health_snapshot (P2-16).

Reads a raw-results dir (or a saved snapshot JSON) and writes a
self-contained board: validity, rotation candidates (saturated +
high-contamination tasks), per-task saturation, contamination levels,
and flakiness. Inline CSS only, no network, no deps.

Usage:
  python3 shared/render_health_board.py results/raw --out reports/health-board/
  open reports/health-board/health-board.html
"""

import datetime
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    import runner
except ImportError:
    from shared import runner


def _load_snapshot(source):
    if os.path.isdir(source):
        return runner.health_snapshot(source)
    with open(source, encoding="utf-8") as f:
        return json.load(f)


def _level_chip(level):
    color = {"low": "#28a745", "elevated": "#fd7e14", "high": "#d63384"}.get(level, "#6c757d")
    return '<span style="background:%s;color:#fff;padding:1px 8px;border-radius:9px">%s</span>' % (
        color,
        html.escape(str(level)),
    )


def render_board(source, outdir):
    """Build health-board.html + .json from a raw dir or snapshot."""
    snap = _load_snapshot(source)
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "health-board.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_utc": generated, "snapshot": snap}, f, ensure_ascii=False, indent=1)
    validity = snap.get("validity") or {}
    contam = snap.get("contamination") or {}
    rows = []
    rows.append(
        "<header><p>EMO-X · benchmark health · maintainer "
        "report</p><h1>Health board <small>%d attempts · "
        "%d models · generated %s</small></h1></header>"
        % (snap.get("n_attempts", 0), snap.get("n_models", 0), generated)
    )
    rows.append("<section><h2>Executive summary</h2>")
    rows.append(
        "<p>Validity: <b>%s</b> · Contamination: %s · "
        "Rotation candidates: <b>%s</b></p>"
        % (
            html.escape(str(validity.get("validity", "?"))),
            _level_chip(contam.get("level", "?")),
            html.escape(", ".join(snap.get("rotation_candidates", [])) or "none"),
        )
    )
    rows.append("</section><section><h2>Per-task detail</h2>")
    rows.append(
        "<table border=1 cellpadding=5><tr><th>Task</th>"
        "<th>Flakiness</th><th>Saturation</th>"
        "<th>Contamination</th><th>Discrimination</th></tr>"
    )
    tasks = snap.get("tasks") or {}
    sat = snap.get("saturation") or {}
    cbt = snap.get("contamination_by_task") or {}
    disc = snap.get("discrimination") or {}
    for task in sorted(set(tasks) | set(sat) | set(cbt) | set(disc)):
        fl = (tasks.get(task) or {}).get("flakiness") or {}
        st = sat.get(task) or {}
        cb = cbt.get(task) or {}
        dc = disc.get(task) or {}
        rows.append(
            "<tr><td>%s</td><td>%s</td><td>%s%s</td><td>%s</td>"
            "<td>%s</td></tr>"
            % (
                html.escape(str(task)),
                html.escape(str(fl.get("flakiness", "?"))),
                "SATURATED " if st.get("saturated") else "",
                html.escape(str(st.get("mean_pass", "?"))),
                _level_chip(cb.get("level", "?")),
                html.escape(str(dc.get("discrimination", "?"))),
            )
        )
    rows.append("</table></section>")
    page = (
        "<html><head><meta charset=utf-8><title>EMO-X health board"
        "</title></head><body>" + "".join(rows) + "</body></html>"
    )
    with open(os.path.join(outdir, "health-board.html"), "w", encoding="utf-8") as f:
        f.write(page)
    return os.path.join(outdir, "health-board.html")


def main(argv=None):
    args = list(argv or [])
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    source = args[0]
    outdir = "reports/health-board"
    if "--out" in args:
        outdir = args[args.index("--out") + 1]
    print(render_board(source, outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
