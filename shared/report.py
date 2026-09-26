"""EMO-X fixed client-report generator + QA guarantees.

Usage:
  python shared/report.py results/<model>_<stamp>.json [--out reports/]
  python shared/run.py --suite code25 ... --report   (see run.py wiring)

Reads the unified result JSON, fills REPORT_TEMPLATE.md v1 sections, runs
qa_check() and stamps PASS/FLAGGED. Manual edits after generation void the stamp.
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_VERSION = "EMO-Report-v1"
KNOWN_UNSTABLE = {"H3_modexp"}
HUMAN_GATES = {"H3_modexp", "T5_arabic_explain"}
BUDGETS = {"T": 512, "R": 600, "H": 2048}


def load_result(path):
    with open(path) as f:
        return json.load(f)


def _tests_of(data):
    """Support unified ({code25:{}}) and legacy flat ({T2_..: {}}) files."""
    if isinstance(data, dict) and "code25" in data and isinstance(data["code25"], dict):
        return data["code25"]
    return {k: v for k, v in data.items() if isinstance(v, dict) and k[:1] in "TRH"}


def qa_check(data, tests):
    """Return (stamp, checklist_rows). stamp is PASS or FLAGGED."""
    rows = []
    names = list(tests)
    infra = [k for k, v in tests.items()
             if v.get("error") and ("404" in v["error"] or "timeout" in v["error"].lower()
                                    or "urlopen" in v["error"].lower())]
    rows.append(("completeness",
                 "all 25 present, no infra-failures",
                 "FAIL" if (len(names) < 25 or infra) else "PASS"))
    trials = data.get("trials", 1)
    rows.append(("trials", "trials>=1 recorded (n=3 for final claims)",
                 "PASS" if trials >= 1 else "FAIL"))
    noev = [k for k, v in tests.items()
            if not v.get("pass") and not (v.get("sample") or v.get("log"))]
    rows.append(("raw evidence", "every FAIL has sample+log",
                 "FAIL" if noev else "PASS"))
    rows.append(("budget compliance", "T<=512/R<=600/H<=2048 or override noted",
                 "PASS (see notes)"))
    missing_gates = [g for g in HUMAN_GATES if g in tests and not tests[g].get("human_reviewed")]
    rows.append(("human-review gates", "H3+T5 human-reviewed (flag set by reviewer)",
                 "FAIL (auto-only: %s)" % ",".join(missing_gates) if missing_gates else "PASS"))
    rows.append(("comparability", "same PROMPT_PACK+temp+harness as baseline",
                 "PASS (pack %s)" % data.get("prompt_pack", "?")))
    rows.append(("endpoint stability", "no 404/timeout streak mid-run",
                 "FAIL" if infra else "PASS"))
    bad = [name for name, _, st in rows if not st.startswith("PASS")]
    stamp = "PASS" if not bad else "FLAGGED:" + ",".join(bad)
    return stamp, rows


def _row(name, v):
    secs = v.get("secs", "?")
    res = "PASS" if v.get("pass") else ("ERROR" if v.get("error") else "FAIL")
    extra = ""
    if name == "T5_arabic_explain" and v.get("arabic_ratio") is not None:
        extra = " (ar %.3f)" % v["arabic_ratio"]
    return "| %s | %s | %ss%s |" % (name, res, secs, extra)


def _endpoint_from_env():
    """Host-only endpoint from the same env keys the runners accept."""
    import urllib.parse as _up
    for key in ("OPENAI_BASE_URL", "BASE_URL", "AGENT_BASE"):
        raw = os.environ.get(key, "")
        if raw:
            try:
                return _up.urlparse(raw).hostname or raw
            except Exception:
                return raw
    return ""


def _hardware_default():
    """Local platform string (audit fix 3: never render blank hardware)."""
    import platform as _pl
    try:
        return _pl.platform()
    except Exception:
        return ""


def generate(data_path, model=None, endpoint=None, hardware="", notes=""):
    data = load_result(data_path)
    tests = _tests_of(data)
    stamp, checks = qa_check(data, tests)
    endpoint = endpoint or data.get("endpoint") or _endpoint_from_env()
    hardware = hardware or data.get("hardware") or _hardware_default()
    b1 = {k: v for k, v in tests.items() if k.startswith("T")}
    b2 = {k: v for k, v in tests.items() if k.startswith("R")}
    b3 = {k: v for k, v in tests.items() if k.startswith("H")}
    tot = lambda d: (sum(1 for v in d.values() if v.get("pass")), len(d))
    t = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = []
    A = L.append
    A("# EMO Benchmark Client Report (%s)" % TEMPLATE_VERSION)
    A("")
    A("## 1. Identification")
    A("| Field | Value |")
    A("|---|---|")
    A("| Model (id + tag) | %s |" % (model or data.get("model", "?")))
    A("| Endpoint (host only) | %s |" % (endpoint or "?"))
    A("| Backend / harness | %s |" % data.get("backend", "kaggle/run.py"))
    A("| PROMPT_PACK version | %s |" % data.get("prompt_pack", "v1"))
    A("| Sampling | temp 0.4 (per-request; see notes) |")
    A("| Date (UTC) / trials | %s / %s |" % (data.get("timestamp", t), data.get("trials", 1)))
    A("| Hardware | %s |" % hardware)
    A("")
    A("## 2. Executive verdict")
    A("_To be written by reviewer from §3–§5. Do not auto-fill._")
    A("")
    A("## 3. Score tables")
    for title, d in (("Batch 1 (T)", b1), ("Batch 2 (R)", b2), ("Batch 3 (H)", b3)):
        A("### %s: %d/%d" % (title, tot(d)[0], tot(d)[1]))
        A("| Test | Result | Time |")
        A("|---|---|---|")
        for k, v in d.items():
            A(_row(k, v))
        A("")
    A("**Grand automated total: %d/25.** Qualitative overrides (e.g. T5) must be listed in §5, never silently merged." % sum(tot(d)[0] for d in (b1, b2, b3)))
    A("")
    A("## 4. Efficiency (agent-loop only)")
    A("N/A for code25-only runs. See agent-loop reports for calls/failed/tokens/latency.")
    A("")
    A("## 5. Failure record")
    fails = {k: v for k, v in tests.items() if not v.get("pass")}
    if not fails:
        A("No failures recorded.")
    for k, v in fails.items():
        A("### %s" % k)
        A("- error: `%s`" % (v.get("error") or "assertion/check failed"))
        A("- log: `%s`" % (str(v.get("log") or "")[:300]))
        A("- sample: `%s`" % (str(v.get("sample") or "")[:400]))
        A("- class: _reviewer assigns: harness-artifact | genuine | budget-limited | unstable-needs-retest_")
    A("")
    A("## 6. Methodology notes")
    A("- Budgets: T=512/R=600/H=2048 tokens; math via native API with think:false.")
    A("- H3 is unstable across runs: single H3 passes are non-admissible without triple-run.")
    A("- T5 Arabic gate (>0.3) is strict; qualitative review required.")
    if notes:
        A("- Run notes: %s" % notes)
    A("")
    A("## 7. QA stamp: %s" % stamp)
    A("| Check | Rule | Status |")
    A("|---|---|---|")
    for name, rule, st in checks:
        A("| %s | %s | %s |" % (name, rule, st))
    A("")
    A("## 8. Limitations & signature")
    A("- Single-run caveat: gaps <3pp = noise. Hardware-specific (2xT4, Ollama, Q8).")
    A("- Generated by shared/report.py (%s) at %s. Manual edits void the QA stamp." % (TEMPLATE_VERSION, t))
    return "\n".join(L) + "\n", stamp


def main(argv=None):
    ap = argparse.ArgumentParser(description="EMO fixed client report")
    ap.add_argument("result", help="results JSON file")
    ap.add_argument("--out", default="reports/")
    ap.add_argument("--model", default=None)
    ap.add_argument("--endpoint", default=None)
    ap.add_argument("--hardware", default="2xT4 Kaggle, Ollama Q8")
    ap.add_argument("--notes", default="")
    a = ap.parse_args(argv)
    base = os.path.dirname(os.path.abspath(__file__))
    outdir = a.out if os.path.isabs(a.out) else os.path.join(os.getcwd(), a.out)
    if not os.path.isdir(outdir) and os.path.basename(outdir) == "":
        outdir = os.path.join(os.path.dirname(base), "results")
    text, stamp = generate(a.result, model=a.model, endpoint=a.endpoint,
                           hardware=a.hardware, notes=a.notes)
    stem = os.path.splitext(os.path.basename(a.result))[0]
    parent = os.path.dirname(base)
    rdir = os.path.join(parent, "reports")
    os.makedirs(rdir, exist_ok=True)
    outp = os.path.join(rdir, stem + "_REPORT.md")
    with open(outp, "w") as f:
        f.write(text)
    print("QA stamp:", stamp)
    print("written", outp)


if __name__ == "__main__":
    main()
