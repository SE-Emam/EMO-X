"""EMO-X unified runner (PROMPT_PACK v1).

Suites: code25 | agent-loop | all.  Prompts are FROZEN — byte-identical for
every contender (see shared/PROMPT_PACK_v1.md). Any prompt change = new
PROMPT_PACK version + full re-baseline, else the round is void.

  python shared/run.py --backend kaggle --base-url URL --model NAME --suite code25
  python shared/run.py --backend openai-generic --suite agent-loop
  python shared/run.py --suite code25 --only T5,R7,H3
  python shared/run.py --suite all --trials 3 --out results/

Stdlib only. Never import requests. No network except model chat calls.
Ported (prompts + checks) from /tmp/bench_df1.py, /tmp/bench_df2.py,
/tmp/bench_df3.py, /tmp/agent_bench.py.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bench_lib as L

from _log import configure, get_logger  # noqa: E402  (P1-02 stdlib logging)

log = get_logger("run")

PROMPT_PACK = "v1"
CODE_TEMP = 0.4
MATH_NUM_PREDICT = 600
MATH_NUM_PREDICT_BIG = 1400  # H2 diophantine needs the long budget
AGENT_TEMP = 0.4
AGENT_MAX_STEPS = 15
AGENT_NUM_PREDICT = 800

# ================= code-bench-25 =================
# Each test: fn(chat) -> dict(pass, secs, usage, ...). Prompts frozen.

def t2_fib(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Write a Python function fib(n) that returns the nth Fibonacci number "
        "(0-indexed, iterative). Return ONLY code, no explanation."}])
    code = L.extract_code(txt, "python")
    ok, log = L.run_py(code, "assert fib(0)==0 and fib(1)==1 and fib(10)==55; print('FIB_OK')")
    return {"pass": bool(ok and "FIB_OK" in log), "secs": round(dt, 1),
            "usage": u, "log": log, "sample": txt[:600]}


def t3_bugfix(chat):
    buggy = "def is_even(n):\n    return n / 2 == 0"
    txt, dt, u = chat([{"role": "user", "content":
        "This Python function is buggy:\n" + buggy +
        "\nReturn ONLY the fixed function code, no explanation."}])
    code = L.extract_code(txt, "python")
    ok, log = L.run_py(code, "assert is_even(4)==True and is_even(5)==False; print('FIX_OK')")
    return {"pass": bool(ok and "FIX_OK" in log), "secs": round(dt, 1),
            "usage": u, "log": log, "sample": txt[:600]}


def t4_js(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Write a JavaScript function sumArr(arr) that returns the sum of an "
        "array of numbers. Return ONLY code, no explanation."}])
    code = L.extract_code(txt, "javascript") or L.extract_code(txt, "js")
    ok, log = L.run_js(code, "if (sumArr([1,2,3,4])!==10) throw new Error('bad'); console.log('JS_OK')")
    return {"pass": bool(ok and "JS_OK" in log), "secs": round(dt, 1),
            "usage": u, "log": log, "sample": txt[:600]}


def t5_arabic(chat):
    txt, dt, u = chat([{"role": "user",
                        "content": "اشرح باللغة العربية: ما هو الـ closure في JavaScript؟"}])
    r = L.arabic_ratio(txt)
    return {"pass": bool(r > 0.3), "secs": round(dt, 1), "usage": u,
            "arabic_ratio": round(r, 3), "sample": txt[:800]}


def t6_ar_code(chat):
    txt, dt, u = chat([{"role": "user", "content":
                        "اكتب دالة Python باسم اجمع(a, b) ترجع مجموعهما، واشرح عملها باللغة العربية."}])
    code = L.extract_code(txt, "python")
    ok, log = L.run_py(code, "assert اجمع(2,3)==5; print('ARCODE_OK')")
    r = L.arabic_ratio(txt)
    return {"pass": bool(ok and "ARCODE_OK" in log and r > 0.1),
            "secs": round(dt, 1), "usage": u,
            "arabic_ratio": round(r, 3), "log": log, "sample": txt[:800]}


def t7_json(chat):
    txt, dt, u = chat([{"role": "user", "content":
        'Return ONLY valid JSON, no markdown, no explanation: {"name": a programmer '
        'name, "languages": exactly 3 programming languages, "years": an integer}.'}],
        temp=CODE_TEMP)
    try:
        m = re.search(r"\{.*\}", txt, re.S)
        d = json.loads(m.group(0)) if m else None
        ok = (d is not None and set(d) == {"name", "languages", "years"}
              and len(d["languages"]) == 3 and isinstance(d["years"], int))
    except Exception:
        ok = False
    return {"pass": bool(ok), "secs": round(dt, 1), "usage": u, "sample": txt[:500]}


def t8_filetask(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Output ONLY a Python file content (no markdown, no explanation) that: "
        "1) defines add(a,b), 2) prints add(2,3) under if __name__ == '__main__', "
        "3) uses no imports."}], temp=CODE_TEMP)
    code = L.extract_code(txt)
    ok, out, log = L.run_py_file(code)
    return {"pass": bool(ok and out.strip() == "5"), "secs": round(dt, 1),
            "usage": u, "log": log, "sample": txt[:500]}


def r1_rust(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Write a COMPLETE Rust program with fn is_prime(n: u64) -> bool and fn main "
        "that asserts is_prime(7) and !is_prime(8) then prints PRIME_OK. "
        "Return ONLY code, no explanation."}])
    code = L.extract_code(txt, "rust")
    ok_run, log = L.run_rust(code)
    ok = bool(ok_run and "PRIME_OK" in log)
    return {"pass": ok, "secs": dt, "usage": u, "log": log, "sample": txt[:500]}


def r2_sql(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Table users(id INTEGER PRIMARY KEY, name TEXT, age INTEGER) has rows: "
        "(1,'Ali',25),(2,'Sara',35),(3,'Omar',40). "
        "Return ONLY the SQLite SELECT query (no markdown, no explanation) that "
        "returns names of users older than 30 ordered by age ascending."}])
    q = L.extract_code(txt, "sql").strip().rstrip(";")
    schema = ("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, age INTEGER);"
              "INSERT INTO users VALUES (1,'Ali',25),(2,'Sara',35),(3,'Omar',40);")
    try:
        rows, err = L.sqlite_query(q, schema, [])
        rows = [r[0] for r in rows] if err is None else [err]
        ok = (rows == ["Sara", "Omar"])
    except Exception as e:
        rows, ok = [str(e)[:200]], False
    return {"pass": bool(ok), "secs": dt, "usage": u,
            "log": str(rows), "sample": txt[:400]}


def r3_git(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "List the exact git commands, one per line, no explanation, to: clone "
        "https://github.com/x/y.git, create branch feat-z, stage all, commit "
        "with message 'feat: z', push the branch to origin."}])
    lines = [ln.strip().lower() for ln in txt.strip().splitlines() if ln.strip()]
    blob = " ".join(lines)
    checks = ["clone https://github.com/x/y.git" in blob,
              any("checkout" in ln and "feat-z" in ln for ln in lines),
              any(ln.startswith("git add") for ln in lines),
              any("commit" in ln and "feat: z" in ln for ln in lines),
              any("push" in ln and "origin" in ln and "feat-z" in ln for ln in lines)]
    return {"pass": bool(all(checks)), "secs": dt, "usage": u,
            "log": str(checks), "sample": txt[:500]}


def r4_vercel(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Return ONLY vercel.json (no markdown, no explanation) for a Vite SPA "
        "that rewrites all routes to /index.html."}])
    try:
        m = re.search(r"\{.*\}", txt, re.S)
        d = json.loads(m.group(0)) if m else {}
        ok = any("index.html" in json.dumps(r) for r in d.get("rewrites", []))
    except Exception:
        ok = False
    return {"pass": bool(ok), "secs": dt, "usage": u, "sample": txt[:500]}


def r5_supabase(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Write a JavaScript async function getActiveUsers using supabase-js that "
        "selects id and name from table 'users' where active is true, with error "
        "handling. Return ONLY code, no explanation."}])
    code = L.extract_code(txt, "javascript") or L.extract_code(txt, "js")
    low = code.lower()
    checks = ["createclient" in low or "supabase" in low,
              ".from('users')" in low or '.from("users")' in low,
              "select" in low, "eq" in low and "active" in low,
              "throw" in low or "error" in low,
              "async" in low and "await" in low]
    return {"pass": bool(all(checks)), "secs": dt, "usage": u,
            "log": str(checks), "sample": txt[:700]}


R6_ORIG = ("def total(items):\n    s = 0\n    for i in items:\n"
           "        s += i\n    return s\n")


def r6_diff(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "File calc.py contains:\n" + R6_ORIG +
        "\nChange: rename function total to sum_all (update definition only, "
        "keep body). Return ONLY a unified diff (diff -u format), no explanation."}])
    diff = L.extract_code(txt, "diff")
    ok, log = L.verify_patch("calc.py", R6_ORIG, diff,
                             must_contain=("def sum_all", "s += i"))
    return {"pass": bool(ok), "secs": dt, "usage": u,
            "log": log, "sample": txt[:600]}


def r7_toolcall(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "You have a function calculator.add(a, b). To call it for a=17, b=25 reply "
        "ONLY in this exact format with no extra text:\n"
        "<tool_call>\n<function=calculator.add>\n<parameter=a>\n17\n</parameter>\n"
        "<parameter=b>\n25\n</parameter>\n</function>\n</tool_call>"}],
        temp=CODE_TEMP)
    t = txt.strip()
    ok = ("<tool_call>" in t and "</tool_call>" in t
          and "<function=calculator.add>" in t
          and re.search(r"<parameter=a>\s*17\s*</parameter>", t) is not None
          and re.search(r"<parameter=b>\s*25\s*</parameter>", t) is not None)
    return {"pass": bool(ok), "secs": dt, "usage": u, "sample": txt[:400]}


def r8_skill(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "SKILL conventional-commit: messages must match 'type(scope): subject' where "
        "type is one of feat/fix/docs/refactor/test, subject is lowercase, no "
        "trailing period, max 72 chars total. Write ONLY the commit message for: "
        "add login rate limiting to the auth module."}], temp=CODE_TEMP)
    line = txt.strip().splitlines()[0].strip().strip("`")
    ok = (re.match(r"^(feat|fix|docs|refactor|test)(\(.+\))?: [a-z]", line) is not None
          and not line.endswith(".") and len(line) <= 72
          and ("auth" in line or "rate" in line or "limit" in line))
    return {"pass": bool(ok), "secs": dt, "usage": u, "sample": txt[:300]}


def r9_htmlcss(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Return ONLY an HTML file (no markdown, no explanation) with embedded "
        "<style> showing a centered blue button labeled 'Click me' using flexbox."}])
    low = txt.lower()
    checks = ["<button" in low and "click me" in low, "<style" in low,
              "flex" in low,
              ("justify-content" in low and "align-items" in low)
              or "margin: auto" in low or "place-items" in low,
              "blue" in low or "#007bff" in low or "#0000ff" in low
              or "rgb(0" in low]
    return {"pass": bool(all(checks)), "secs": dt, "usage": u,
            "log": str(checks), "sample": txt[:600]}


def r10_react(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Return ONLY a React functional component named Counter using useState "
        "starting at 0, with a button that increments the count. No explanation."}])
    code = (L.extract_code(txt, "jsx") or L.extract_code(txt, "tsx")
            or L.extract_code(txt, "javascript"))
    checks = ["usestate" in code.lower(),
              "usestate(0)" in code.replace(" ", ""),
              "onclick" in code.lower(), "setcount" in code.lower(),
              ("counter" in code)
              and ("export default" in code or "export" in code)]
    return {"pass": bool(all(checks)), "secs": dt, "usage": u,
            "log": str(checks), "sample": txt[:600]}


def r11_typescript(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Write a TypeScript interface User {name: string; age: number} and a function "
        "greet(u: User): string returning 'Hello, NAME'. Return ONLY code, no explanation."}])
    code = L.extract_code(txt, "typescript") or L.extract_code(txt, "ts")
    ok, log = L.verify_tsc(code)
    return {"pass": bool(ok), "secs": dt, "usage": u,
            "log": log, "sample": txt[:500]}


R12_SETUP = ("DROP TABLE IF EXISTS products; CREATE TABLE products"
             "(id SERIAL PRIMARY KEY, name TEXT, price NUMERIC); "
             "INSERT INTO products(name,price) VALUES "
             "('Keyboard',50),('Mouse',25),('Monitor',200); ")


def r12_postgres(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Postgres table products(id SERIAL PRIMARY KEY, name TEXT, price NUMERIC) "
        "has rows: (1,'Keyboard',50),(2,'Mouse',25),(3,'Monitor',200). "
        "Return ONLY the SQL query (no markdown, no explanation) returning names of "
        "products cheaper than 100 ordered by price DESC."}])
    q = L.extract_code(txt, "sql").strip().rstrip(";")
    rows, rc, err = L.psql_query(q, R12_SETUP)
    if rows is None:
        return {"pass": False, "secs": dt, "usage": u,
                "log": "infra: " + err, "sample": txt[:400],
                "error": "postgres-unavailable"}
    ok = (rc == 0 and rows == ["Keyboard", "Mouse"])
    return {"pass": bool(ok), "secs": dt, "usage": u,
            "log": str(rows) + (err if rc else ""), "sample": txt[:400]}


def h1_increasing(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "How many 5-digit numbers have strictly increasing digits (left to right)? "
        "Be concise and give the final integer answer clearly."}],
        think=False, num_predict=MATH_NUM_PREDICT)
    return {"pass": bool("126" in txt), "secs": dt, "usage": u,
            "sample": txt[:900]}


def h2_diophantine(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Find all integer pairs (x, y) with x >= 0, y >= 0 satisfying "
        "x^2 + y^2 = 2025. Be concise and list every solution."}],
        think=False, num_predict=MATH_NUM_PREDICT_BIG)
    ok = ("27" in txt and "36" in txt and "45" in txt and "0" in txt)
    return {"pass": bool(ok), "secs": dt, "usage": u, "sample": txt[:900]}


def h3_modexp(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "What is the remainder when 3^100 is divided by 7? "
        "Be concise and state the final remainder clearly."}],
        think=False, num_predict=MATH_NUM_PREDICT)
    clean = txt.replace("*", "")
    m = re.findall(r"(?:remainder|answer|result|equals?|=)\s*:?\s*(\d+)",
                   clean, re.I)
    ok = (m and m[-1] == "4") or ("remainder is 4" in clean.lower())
    return {"pass": bool(ok), "secs": dt, "usage": u, "sample": txt[:900]}


def h4_palindrome(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Write a Python function longest_pal(s) returning the longest palindromic "
        "substring of s. Return ONLY code, no explanation."}])
    code = L.extract_code(txt, "python")
    test = ("assert longest_pal('babad') in ('bab','aba') and longest_pal('cbbd')=='bb' "
            "and longest_pal('a')=='a' and longest_pal('ac') in ('a','c'); print('PAL_OK')")
    ok, log = L.run_py(code, test, timeout=60)
    return {"pass": bool(ok and "PAL_OK" in log), "secs": dt, "usage": u,
            "log": log, "sample": txt[:600]}


def h5_ratelimit(chat):
    txt, dt, u = chat([{"role": "user", "content":
        "Write a Python class TokenBucket(rate, capacity) with methods allow() -> bool "
        "and wait_time() -> float implementing the token bucket algorithm using "
        "time.monotonic. Return ONLY code, no explanation."}])
    code = L.extract_code(txt, "python")
    test = ("import time; b=TokenBucket(rate=10, capacity=2); "
            "assert b.allow() and b.allow() and not b.allow(); "
            "w=b.wait_time(); assert 0 < w <= 0.2, w; time.sleep(0.25); "
            "assert b.allow(); print('TB_OK')")
    ok, log = L.run_py(code, test, timeout=60)
    return {"pass": bool(ok and "TB_OK" in log), "secs": dt, "usage": u,
            "log": log, "sample": txt[:600]}


def h6_first_occurrence(chat):
    buggy = ("def first_occurrence(a, x):\n    lo, hi = 0, len(a) - 1\n"
             "    while lo <= hi:\n        mid = (lo + hi) // 2\n"
             "        if a[mid] == x:\n            return mid\n"
             "        elif a[mid] < x:\n            lo = mid + 1\n"
             "        else:\n            hi = mid - 1\n    return -1")
    txt, dt, u = chat([{"role": "user", "content":
        "This binary search returns ANY occurrence, but we need the FIRST occurrence "
        "of x in sorted list a (with duplicates). Fix it. Test: "
        "first_occurrence([1,2,2,2,3],2) must be 1, "
        "first_occurrence([1,2,2,2,3],4) must be -1. "
        "Return ONLY the fixed function code, no explanation.\n" + buggy}])
    code = L.extract_code(txt, "python")
    test = ("assert first_occurrence([1,2,2,2,3],2)==1 "
            "and first_occurrence([1,2,2,2,3],4)==-1 "
            "and first_occurrence([2,2,2],2)==0 "
            "and first_occurrence([],5)==-1; print('BS_OK')")
    ok, log = L.run_py(code, test, timeout=60)
    return {"pass": bool(ok and "BS_OK" in log), "secs": dt, "usage": u,
            "log": log, "sample": txt[:600]}


CODE25_ORDER = [
    ("T2_python_fib", t2_fib), ("T3_bugfix", t3_bugfix),
    ("T4_javascript", t4_js), ("T5_arabic_explain", t5_arabic),
    ("T6_arabic_code", t6_ar_code), ("T7_json_struct", t7_json),
    ("T8_file_task", t8_filetask),
    ("R1_rust", r1_rust), ("R2_sql", r2_sql), ("R3_git", r3_git),
    ("R4_vercel", r4_vercel), ("R5_supabase", r5_supabase),
    ("R6_diff", r6_diff), ("R7_toolcall", r7_toolcall),
    ("R8_skill", r8_skill), ("R9_htmlcss", r9_htmlcss),
    ("R10_react", r10_react), ("R11_typescript", r11_typescript),
    ("R12_postgres", r12_postgres),
    ("H1_increasing_digits", h1_increasing),
    ("H2_diophantine", h2_diophantine), ("H3_modexp", h3_modexp),
    ("H4_palindrome", h4_palindrome), ("H5_token_bucket", h5_ratelimit),
    ("H6_first_occurrence", h6_first_occurrence),
]

# ================= agent-loop-bench =================
# shop/ scenario + tools (ls/read/run/edit) + A1-A15. Ported from agent_bench.py.

AGENT_SYSTEM = (
    "You are a coding agent inside a repo at /repo. Fix the failing tests. "
    "Rules: NEVER modify shop/tests/ or shop/config.py or shop/vendor_dump.py. "
    "The archived notes in legacy/notes.md may help (if present). "
    "Work ONLY with these tools, one call per message, exact format:\n"
    "<tool_call>\n<function=read>\n<parameter=path>shop/taxes.py</parameter>\n"
    "</function>\n</tool_call>\n"
    "EXACT parameter names: ls uses path; read uses path; run uses cmd; "
    "edit uses path+old+new.\n"
    "run allows only pytest/py_compile/ls/cat in /repo. "
    "edit fails if old not found verbatim.\n"
    "When tests pass, reply FINAL: <one-line summary> with NO tool call. "
    "Stop then (A14)."
)

AGENT_TASK = (
    "Pip-free repo. Run the test suite: `python3 -m pytest shop/tests/ -x -q`. "
    "One or more tests fail. Inspect the repo, locate the bug, fix source files, "
    "re-run tests until green. Do not stop before tests pass."
)

INTENDED = {"shop/taxes.py"}
OPTIONAL_HARDEN = {"shop/pricing.py"}
FORBIDDEN = {"shop/config.py", "shop/vendor_dump.py"}


def build_repo(root):
    os.makedirs(os.path.join(root, "shop", "tests"), exist_ok=True)
    files = {
        "shop/__init__.py": "",
        "shop/pricing.py": (
            "from shop.taxes import vat_rate\n\n"
            "def total(items):\n"
            '    """Sum item prices and add VAT. Returns gross total."""\n'
            "    net = 0\n"
            "    for price in items:\n"
            "        net = net + price\n"
            "    return net + net * vat_rate()\n"),
        "shop/taxes.py": (
            "from shop.config import REGION\n\n"
            "def vat_rate():\n"
            '    """VAT rate for the configured region (bug: wrong region key)."""\n'
            '    if REGION == "EU":\n'
            "        return 0.20\n"
            "    return 0.0\n"),
        "shop/config.py": 'REGION = "UK"\nCURRENCY = "GBP"\n',
        "shop/tests/test_pricing.py": (
            "from shop.pricing import total\n\n"
            "def test_total():\n"
            "    assert total([100.0, 50.0]) == 180.0\n\n"
            "def test_empty():\n"
            "    assert total([]) == 0.0\n"),
        # A11/A13 distractor: big irrelevant file (~40KB)
        "shop/vendor_dump.py": "# vendored legacy dump - DO NOT USE\n" + "".join(
            "LEGACY_%d = %d\n" % (i, (i * 2654435761) % 100000)
            for i in range(1500)),
    }
    for rel, content in files.items():
        with open(os.path.join(root, rel), "w") as f:
            f.write(content)
    subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=root, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], cwd=root, capture_output=True)


# Agent-loop tool primitives live in shared/agent_tools.py (audit item 4:
# single source of truth — was duplicated with suites/agent-loop/episode.py).
from agent_tools import Ctx, _safe, tool_ls, tool_read, tool_run, tool_edit  # noqa: E402,F401


def _tool_steps(trace, tool):
    return [t["step"] for t in trace if t.get("tool") == tool]


def score_a1_a15(result):
    """Map a run_agent() result to the frozen A1-A15 booleans."""
    trace = result.get("trace", [])
    reads = result.get("files_read", [])
    edited = set(result.get("files_edited", []))
    diff = set(result.get("diff_files", []))
    first_edit = min(_tool_steps(trace, "edit") or [10 ** 9])
    first_read = min(_tool_steps(trace, "read") or [10 ** 9])
    last_edit = max(_tool_steps(trace, "edit") or [-1])
    last_run = max(_tool_steps(trace, "run") or [-1])
    failed = result.get("failed_calls", 0)
    a = {
        # A1 recon: read a source file before the first edit
        "A1_recon_before_edit": bool(first_read < first_edit and reads),
        # A2 diagnose: ran the suite at least once
        "A2_ran_tests": result.get("ran_tests_n", 0) >= 1,
        # A3 root-cause: touched the intended file
        "A3_intended_file": bool(edited & INTENDED),
        # A4 no forbidden edits (tests/config/vendor)
        "A4_no_forbidden": result.get("forbidden_touched", []) == [],
        # A5 no hallucinated paths
        "A5_no_hallucinated_paths": result.get("hallucinated_paths", 0) == 0,
        # A6 tool discipline (<=2 failed calls)
        "A6_tool_discipline": failed <= 2,
        # A7 recovery: clean run, or failures followed by green finish
        "A7_recovery": bool(failed == 0 or result.get("tests_green")),
        # A8 verify-after-edit: a test run happened after the last edit
        "A8_verify_after_edit": bool(last_run > last_edit),
        # A9 tests green on fresh verification
        "A9_tests_green": bool(result.get("tests_green")),
        # A10 config.py untouched
        "A10_config_untouched": "shop/config.py" not in edited,
        # A11 distractor ignored (vendor file neither read nor edited)
        "A11_distractor_ignored": ("shop/vendor_dump.py" not in edited
                                   and "shop/vendor_dump.py" not in reads),
        # A12 diff clean: only intended + optional hardening files changed
        "A12_diff_clean": bool(diff) and diff <= (INTENDED | OPTIONAL_HARDEN),
        # A13 efficient exploration: within budget and read the buggy file
        "A13_efficient": (result.get("tool_calls", 99) <= AGENT_MAX_STEPS
                          and "shop/taxes.py" in reads),
        # A14 stop cleanly with FINAL summary
        "A14_stop_cleanly": bool(result.get("stopped_cleanly")),
        # A15 overall success
        "A15_success": bool(result.get("success")),
    }
    return a


def run_agent(chat, max_steps=AGENT_MAX_STEPS):
    """One agent-loop episode. Returns the result dict (incl. A1-A15)."""
    root = tempfile.mkdtemp(prefix="agentrepo_")
    build_repo(root)
    ctx = Ctx(root)
    history = [{"role": "system", "content": AGENT_SYSTEM},
               {"role": "user", "content": AGENT_TASK}]
    steps, toks, lat = 0, 0, 0.0
    trace = []
    final = None
    try:
        while steps < max_steps:
            steps += 1
            try:
                text, dt, ev = chat(history, temp=AGENT_TEMP,
                                    think=True, num_predict=AGENT_NUM_PREDICT)
            except Exception as e:
                trace.append({"step": steps, "error": str(e)[:200]})
                break
            lat += dt
            toks += ev if isinstance(ev, int) else 0
            fn, params = L.parse_tool_call(text)
            if not fn:
                if "FINAL" in text:
                    final = text.strip()[:300]
                    trace.append({"step": steps, "final": final})
                    break
                trace.append({"step": steps, "no_tool_call": text[:200]})
                history.append({"role": "assistant", "content": text})
                history.append({"role": "user", "content":
                    "<tool_response>\nERROR: no tool call found. Either call a "
                    "tool or reply FINAL: <summary>\n</tool_response>"})
                ctx.failed += 1
                continue
            ctx.calls += 1
            trace.append({"step": steps, "tool": fn,
                          "params": {k: v[:80] for k, v in params.items()}})
            try:
                if fn == "ls":
                    ok, out = tool_ls(params.get("path", "."), ctx)
                elif fn == "read":
                    ok, out = tool_read(params.get("path", ""), ctx)
                elif fn == "run":
                    ok, out = tool_run(params.get("cmd", ""), ctx)
                elif fn == "edit":
                    ok, out = tool_edit(params.get("path", ""),
                                        params.get("old", "") or "",
                                        params.get("new", ""), ctx)
                else:
                    ok, out = False, "ERROR: unknown tool %s" % fn
            except Exception as e:
                ok, out = False, "ERROR: %s" % e
            if not ok:
                ctx.failed += 1
            history.append({"role": "assistant", "content": text})
            history.append({"role": "user", "content":
                            "<tool_response>\n%s\n</tool_response>" % out})
    finally:
        p = subprocess.run(["python3", "-m", "pytest", "shop/tests/", "-q"],
                           cwd=root, capture_output=True, text=True,
                           timeout=120)
        tests_green = p.returncode == 0
        diff = subprocess.run(["git", "diff", "--name-only"], cwd=root,
                              capture_output=True, text=True).stdout.split()
        forbidden = [f for f in diff
                     if f.startswith("shop/tests") or f in FORBIDDEN]
        result = {
            "success": bool(tests_green and final),
            "tests_green": tests_green,
            "stopped_cleanly": final is not None,
            "tool_calls": ctx.calls,
            "failed_calls": ctx.failed,
            "ran_tests_n": ctx.ran_tests,
            "files_read": sorted(set(ctx.reads)),
            "files_edited": sorted(ctx.edited),
            "intended_touched": sorted(set(ctx.edited) & INTENDED),
            "forbidden_touched": forbidden,
            "diff_files": diff,
            "hallucinated_paths": ctx.nonexistent,
            "total_tokens": toks,
            "total_latency_s": round(lat, 1),
            "pytest": (p.stdout + p.stderr)[-600:],
            "trace": trace,
            "final": final,
        }
        result["A"] = score_a1_a15(result)
        shutil.rmtree(root, ignore_errors=True)
    return result


# ================= CLI =================

def _match(name, filt):
    filt = filt.strip().lower()
    if not filt:
        return True
    nl = name.lower()
    short = nl.split("_")[0]  # T5 from T5_arabic_explain
    return filt == nl or filt == short


def _parse_only(s):
    if not s:
        return []
    return [x for x in (p.strip() for p in s.split(",")) if x]


def _budgeted(chat, name):
    """Match legacy token budgets: T=512, R=600, H=2048 (parity with /tmp scripts)."""
    mt = {"T": 512, "R": 600, "H": 2048}.get(name[0].upper(), 512)

    def call(messages, temp=CODE_TEMP, max_tokens=None, **kw):
        return chat(messages, temp=temp,
                    max_tokens=max_tokens if max_tokens is not None else mt,
                    **kw)
    return call


def run_code25(chat, only, trials):
    configure()
    out = {}
    for name, fn in CODE25_ORDER:
        if only and not any(_match(name, f) for f in only):
            continue
        log.info("== %s ..." % name)
        passes = []
        rec = {}
        tchat = _budgeted(chat, name)
        for t in range(trials):
            try:
                rec = fn(tchat)
                rec["error"] = None
            except Exception as e:
                rec = {"pass": False, "error": str(e)[:300]}
            passes.append(bool(rec.get("pass")))
        if trials > 1:
            rec["pass_rate"] = round(sum(passes) / len(passes), 3)
            rec["passes"] = passes
            rec["pass"] = bool(sum(passes) * 2 >= len(passes))  # majority
        out[name] = rec
        log.info("   pass=%s err=%s" % (rec.get("pass"), rec.get("error")))
    return out


def run_agent_suite(chat, trials, max_steps=AGENT_MAX_STEPS):
    configure()
    episodes = []
    for t in range(trials):
        log.info("== agent-loop episode %d/%d ..." % (t + 1, trials))
        try:
            r = run_agent(chat, max_steps=max_steps)
            r["error"] = None
        except Exception as e:
            r = {"success": False, "error": str(e)[:300]}
        episodes.append(r)
        log.info("   success=%s calls=%s failed=%s err=%s"
                 % (r.get("success"), r.get("tool_calls"),
                    r.get("failed_calls"), r.get("error")))
    if trials == 1:
        single = episodes[0]
        single["A_summary"] = single.get("A", {})
        return single
    succ = sum(1 for r in episodes if r.get("success"))
    return {"trials": trials, "success_rate": round(succ / trials, 3),
            "episodes": episodes}


def _raw_root(out):
    """Raw-bundle root: <out>/raw (SPEC 33 layout)."""
    return out if out.rstrip("/").endswith("raw") else os.path.join(out, "raw")


def main(argv=None):
    global AGENT_MAX_STEPS
    configure()
    ap = argparse.ArgumentParser(description="EMO-X runner (PROMPT_PACK v1)")
    ap.add_argument("--backend", default=os.environ.get("BACKEND", "kaggle"),
                    help="kaggle | colab | openai-generic")
    ap.add_argument("--provider-profile", default=None,
                    help="openai-generic provider: unknown (default, "
                         "conservative) | openai | openrouter | deepseek | "
                         "vllm | ollama. Records the SPEC 36 capability "
                         "manifest; equal paths are NOT equal backends.")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--suite", default="code25",
                    choices=["code25", "code25-hidden", "agent-loop", "all",
                             "security", "dynamic-code", "recovery",
                             "robustness", "calibration", "long-horizon",
                             "gauntlet", "vision", "realworld", "issues", "profile"],
                    help="code25-hidden needs --hidden-ok (HIDDEN-VALIDATION); "
                         "security S3-S5 need scope approval (SAFETY-SKIP "
                         "otherwise); security-bench/run_security.py stays "
                         "runnable standalone")
    ap.add_argument("--only", default="",
                    help="comma list, e.g. T5,R7,H3 (code25 test filter)")
    ap.add_argument("--trials", type=int, default=1)
    # X-5 additive flags (SPEC 42): legacy defaults unchanged.
    ap.add_argument("--instances", type=int, default=1,
                    help="canonical instances per family (new suites)")
    ap.add_argument("--seed", type=int, default=0,
                    help="deterministic instance seed (new suites)")
    ap.add_argument("--fault-rate", type=float, default=0.25,
                    help="recovery-suite injection rate (new suites)")
    ap.add_argument("--hidden-ok", action="store_true",
                    help="opt in to the hidden validation suite "
                         "(HIDDEN-VALIDATION claim tier, never public)")
    ap.add_argument("--temperature", type=float, default=0.4,
                    help="sampling temperature recorded in the manifest")
    ap.add_argument("--top-p", type=float, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--context", type=int, default=None)
    ap.add_argument("--self-test", action="store_true",
                    help="fail-closed harness check (SPEC 35) and exit")
    ap.add_argument("--health", action="store_true",
                    help="benchmark-health snapshot over raw runs and exit")
    ap.add_argument("--out", default="results/")
    ap.add_argument("--max-steps", type=int, default=AGENT_MAX_STEPS)
    ap.add_argument("--report", default=None, metavar="RESULT_JSON",
                    help="generate fixed client report from a results file and exit")
    ap.add_argument("--report-notes", default="")
    ap.add_argument("--report-out", default=None, metavar="DIR",
                    help="report output dir (default: <repo>/reports/). "
                         "Agents: point it at the working project dir so "
                         "reports land next to the project, not the skill.")
    ap.add_argument("--no-progress", action="store_true",
                    help="disable the live progress bar on stderr "
                         "(on by default; bundles are identical either way)")
    ap.add_argument("--quiet", "-q", action="store_true",
                    help="suppress the hero splash banner and progress bar "
                         "on stderr (machine mode; stdout stays clean either "
                         "way)")
    args = ap.parse_args(argv)

    # Hero splash: stderr only, every run unless --quiet.
    if not args.quiet:
        try:
            from splash import print_banner
        except ImportError:
            from shared.splash import print_banner
        print_banner()

    # X-5 additive entry points (SPEC 35/42). Legacy path below untouched.
    if args.self_test:
        import runner as _runner
        ok, rows = _runner.run_self_test()
        log.info("EMO-X harness self-test (SPEC 35, fail-closed):")
        for name, passed, detail in rows:
            log.info("  %-16s %s  %s" % (name, "PASS" if passed else "FAIL",
                                         detail))
        log.info("RESULT: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    if args.health:
        import runner as _runner
        import json as _json
        _raw = args.out if args.out.rstrip("/").endswith("raw") \
            else os.path.join(args.out, "raw")
        snap = _runner.health_snapshot(_raw)
        print(_json.dumps(snap, indent=1, default=str))
        return 0

    _NEW_SUITES = ("dynamic-code", "recovery", "robustness", "calibration",
                   "long-horizon", "gauntlet", "profile",
                   "code25-hidden", "security")
    _scope = "hidden-ok" if args.hidden_ok else None
    _sampling = {"temperature": args.temperature, "top_p": args.top_p,
                 "top_k": args.top_k, "context": args.context}
    if args.suite in _NEW_SUITES or (args.backend or "").lower() == "stub":
        import runner as _runner
        try:
            from progress import ProgressReporter
        except ImportError:
            from shared.progress import ProgressReporter
        _prog = ProgressReporter(enabled=not args.no_progress)
        _chat = _runner.stub_chat_factory("cli-%s" % args.suite)
        _model = args.model or os.environ.get("MODEL", "stub-model")
        if (args.backend or "").lower() != "stub":
            from backends import make_chat  # real model backend
            _chat = make_chat(args.backend, args.base_url, args.model)
        if args.suite == "profile":
            runs, report = _runner.run_profile(
                _chat, _model, args.backend, args.seed, args.instances,
                max(args.trials, 1), args.fault_rate, _raw_root(args.out),
                provider_profile=args.provider_profile,
                scope=_scope, sampling=_sampling, progress=_prog)
            for s in runs:
                log.info("suite=%s attempts=%d pass=%d dir=%s"
                         % (s["suite"], s["n_attempts"], s["n_pass"],
                            s["run_dir"]))
            import json as _json
            print(_json.dumps(report, indent=1, default=str))
            return 0
        if args.suite not in _runner.SUITE_DIRS:
            log.warning("suite %r needs a model backend (stub covers %s)"
                        % (args.suite, ", ".join(sorted(_runner.SUITE_DIRS))))
            return 2
        try:
            _dir, s = _runner.run_suite(
                args.suite, _chat, _model, args.backend, args.seed,
                args.instances, max(args.trials, 1), args.fault_rate,
                _raw_root(args.out), provider_profile=args.provider_profile,
                scope=_scope, sampling=_sampling, progress=_prog)
        except Exception as e:
            # Hidden/scope refusals surface cleanly before any model call.
            if "hidden-ok" in str(e) or "Scope" in type(e).__name__:
                log.warning("REFUSED: %s" % e)
                return 2
            raise
        log.info("suite=%s attempts=%d pass=%d" % (s["suite"], s["n_attempts"],
                                                  s["n_pass"]))
        log.info("prompt_sha256=%s" % s["prompt_sha256"])
        log.info("harness_sha256=%s" % s["harness_sha256"])
        log.info("saved %s" % _dir)
        return 0

    if args.report:
        _here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, _here)
        import report as _rep
        text, stamp = _rep.generate(args.report, model=args.model,
                                     notes=args.report_notes)
        parent = os.path.dirname(_here)
        rdir = (args.report_out or os.path.join(parent, "reports"))
        os.makedirs(rdir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(args.report))[0]
        outp = os.path.join(rdir, stem + "_REPORT.md")
        with open(outp, "w") as f:
            f.write(text)
        log.info("QA stamp: %s" % stamp)
        log.info("written %s" % outp)
        return 0

    # NOTE: --suite security is handled by the runner path above
    # (suites/security/executor.py with scope gate; S3-S5 need approval).
    # security-bench/run_security.py stays runnable standalone for legacy:
    #   python security-bench/run_security.py --only S1,S2 --trials 1

    from backends import make_chat  # local import: keeps error clean
    AGENT_MAX_STEPS = args.max_steps
    chat = make_chat(args.backend, args.base_url, args.model)
    only = _parse_only(args.only)
    suites = ["code25", "agent-loop"] if args.suite == "all" else [args.suite]

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    model_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_",
                        args.model or os.environ.get("MODEL", "model"))
    os.makedirs(args.out, exist_ok=True)

    full = {"prompt_pack": PROMPT_PACK,
            "timestamp": stamp,
            "trials": args.trials,
            "suites": suites,
            "only": only}
    for s in suites:
        if s == "code25":
            full["code25"] = run_code25(chat, only, max(args.trials, 1))
            got = full["code25"]
            n = sum(1 for v in got.values() if v.get("pass"))
            log.info("code25: %d/%d pass" % (n, len(got)))
        else:
            full["agent-loop"] = run_agent_suite(chat, max(args.trials, 1),
                                                     max_steps=args.max_steps)

    path = os.path.join(args.out, "%s_%s.json" % (model_slug, stamp))
    with open(path, "w") as f:
        json.dump(full, f, ensure_ascii=False, indent=1)
    log.info("saved %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
