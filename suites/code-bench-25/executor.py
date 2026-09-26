"""Executor glue for suites/code-bench-25 (stdlib only).

Runs canonical cases from cases.py inside shared/sandbox.py and emits
schema-valid raw attempt records (SPEC C4/C83 fields) under
results/raw/RUN-ID/. No scoring here (X-3 owns scoring).

Oracle logic mirrors the legacy checks in shared/run.py (frozen pass
criteria); only the execution substrate changed (bench_lib -> sandbox).

Import note: this module does bare `import cases` / `import instances`
for its siblings. suites/security also ships a cases.py, so consumers
must keep suites/code-bench-25 ahead of suites/security on sys.path
(or load modules by file path).

Usage:
  chat = <callable: (messages, temp=..., ...) -> (text, secs, usage)>
  rec = run_family("H3", chat, run_id="RUN-1", model_id="m", trial_id=1)
  write_raw_run(out_dir, run_manifest, attempts, responses)
"""

import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import sandbox  # noqa: E402
from schemas import validate_attempt, validate_run_manifest  # noqa: E402
from manifests import sha256_bytes, sha256_manifest  # noqa: E402
from backends import reasoning_mode_for  # noqa: E402 (Y-5: attempt mode tag)
import cases  # noqa: E402
import instances  # noqa: E402
try:
    from instance_factory import build_h3_equation, check_h3_equation
except ImportError:  # generators/ on path (runner) or add it (standalone)
    GEN = os.path.normpath(os.path.join(HERE, "..", "..", "generators"))
    if GEN not in sys.path:
        sys.path.insert(0, GEN)
    from instance_factory import build_h3_equation, check_h3_equation

#: Variant classes served by this executor (SPEC 9). Canonical prompts are
#: frozen (PROMPT_PACK v1); H3 additionally serves generated perturbed/novel
#: instances with the same oracle kind (unique modular-equation solution).
#: Runner skips unsupported (family, variant) pairs via TypeError (DEN: a
#: missing variant observation is NA, never zero).
VARIANTS = ("canonical", "perturbed", "novel")

# --- small helpers copied in spirit from shared/bench_lib.py (frozen
# behavior; legacy file untouched). Kept local so this suite never
# imports the legacy CLI-entangled modules.

CODE_FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.S)
CALL_RE = re.compile(
    r"<tool_call>\s*<function=([\w.]+)>\s*(.*?)</function>\s*</tool_call>",
    re.S)
PARAM_RE = re.compile(r"<parameter=([\w]+)>\s*(.*?)\s*</parameter>", re.S)


def extract_code(text, lang=None):
    text = strip_special_tokens(text)
    m = CODE_FENCE_RE.findall(text or "")
    if m:
        if lang:
            for tag, code in m:
                if tag.lower() == lang:
                    return code
        return m[0][1]
    return (text or "").strip()


# --- output hygiene (audit fix: special-token tails) -----------------------
# Mirrors shared/bench_lib.strip_special_tokens (kept local: this suite
# never imports the legacy CLI-entangled modules). Template/chat control
# tokens (e.g. <|im_end|>) are transport artifacts, never model content.

_SPECIAL_TOKEN_RE = re.compile(
    r"<\|(?:im_start|im_end|im_sep|endoftext|end_of_text|eot|eos|bos|pad|unk|mask|sep|cls)\|?>|"
    r"</s>|<s>",
)


def strip_special_tokens(text):
    """Remove chat/template control tokens from a model reply.

    Left in place they corrupt otherwise-correct answers: clean
    TypeScript fails tsc, clean JSON fails json.loads, clean SQL fails
    execution, clean Rust fails rustc. Idempotent; "" for non-strings.
    """
    if not isinstance(text, str):
        return ""
    return _SPECIAL_TOKEN_RE.sub("", text)


def extract_json_object(text):
    """First balanced {...} span, or None.

    Uniform rule for every JSON-accepting family (T7, R4, R12-shape):
    scan for the first '{', then balance braces while respecting
    double-quoted strings and backslash escapes. The old greedy
    r"\\{.*\\}" over-matched trailing tokens into the payload
    (<|im_end|> tails, prose after the object).
    """
    text = strip_special_tokens(text)
    if not isinstance(text, str):
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def arabic_ratio(text):
    text = text or ""
    ar = len(re.findall(r"[\u0600-\u06FF]", text))
    return ar / max(len(text), 1)


def parse_tool_call(text):
    m = CALL_RE.search(text or "")
    if not m:
        return None, {}
    return m.group(1), dict(PARAM_RE.findall(m.group(2)))


# --- execution-backed oracles (sandbox only) -------------------------------

def _py_ok(code, test, timeout=30):
    try:
        return sandbox.run_python_code(code, test, timeout=timeout)
    except sandbox.SandboxTimeout:
        raise
    except Exception as e:
        return False, "executor-error: %s" % str(e)[:200]


def check_family(family, reply):
    """Run the frozen oracle for a family. Returns (passed, log).

    Raises _MissingTool for unavailable executors (caller maps to ERROR,
    never a silent pass). SandboxTimeout propagates (caller maps to
    TIMEOUT).

    Audit fix 1: the reply is stripped of chat/template control tokens
    FIRST (strip_special_tokens) — transport artifacts must never fail
    an otherwise-correct answer. Audit fix 2: every JSON-accepting
    family uses extract_json_object (first balanced span), replacing
    the greedy r"\\{.*\\}" which over-matched trailing tokens/prose.
    """
    reply = strip_special_tokens(reply)
    if family == "T2":
        code = extract_code(reply, "python")
        ok, log = _py_ok(
            code, "assert fib(0)==0 and fib(1)==1 and fib(10)==55; "
                  "print('FIB_OK')")
        return bool(ok and "FIB_OK" in log), log
    if family == "T3":
        code = extract_code(reply, "python")
        ok, log = _py_ok(
            code, "assert is_even(4)==True and is_even(5)==False; "
                  "print('FIX_OK')")
        return bool(ok and "FIX_OK" in log), log
    if family == "T4":
        if shutil.which("node") is None:
            raise _MissingTool("node binary not found")
        code = extract_code(reply, "javascript") or extract_code(reply, "js")
        rc, log = sandbox.run_in_sandbox(
            ["node", "-e", code + "\nif (sumArr([1,2,3,4])!==10) "
             "throw new Error('bad'); console.log('JS_OK')"], timeout=30)
        return bool(rc == 0 and "JS_OK" in log), log
    if family == "T5":
        r = arabic_ratio(reply)
        return bool(r > 0.3), "arabic_ratio=%.3f" % r
    if family == "T6":
        code = extract_code(reply, "python")
        ok, log = _py_ok(code, "assert اجمع(2,3)==5; print('ARCODE_OK')")
        r = arabic_ratio(reply)
        return bool(ok and "ARCODE_OK" in log and r > 0.1), \
            "%s arabic_ratio=%.3f" % (log, r)
    if family == "T7":
        try:
            obj = extract_json_object(reply)
            d = json.loads(obj) if obj else None
            ok = (d is not None and set(d) == {"name", "languages", "years"}
                  and len(d["languages"]) == 3
                  and isinstance(d["years"], int))
        except Exception:
            ok = False
        return bool(ok), "json-struct-check"
    if family == "T8":
        code = extract_code(reply)
        root = sandbox.create_sandbox()
        try:
            p = subprocess.run(["python3", "-c", code], cwd=root,
                               capture_output=True, text=True, timeout=30)
            ok = p.returncode == 0 and p.stdout.strip() == "5"
            return ok, (p.stdout + p.stderr)[-500:]
        finally:
            sandbox.destroy_sandbox(root)
    if family == "R1":
        if shutil.which("rustc") is None:
            raise _MissingTool("rustc binary not found")
        code = extract_code(reply, "rust")
        root = sandbox.create_sandbox()
        try:
            src = os.path.join(root, "t.rs")
            exe = os.path.join(root, "t")
            with open(src, "w") as f:
                f.write(code)
            c = subprocess.run(["rustc", "-O", src, "-o", exe],
                               capture_output=True, text=True, timeout=120)
            if c.returncode != 0:
                return False, c.stderr[-400:]
            p = subprocess.run([exe], capture_output=True, text=True,
                               timeout=30)
            log = (p.stdout + p.stderr)[-300:]
            return bool(p.returncode == 0 and "PRIME_OK" in log), log
        finally:
            sandbox.destroy_sandbox(root)
    if family == "R2":
        q = extract_code(reply, "sql").strip().rstrip(";")
        schema = ("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, age INTEGER);"
                  "INSERT INTO users VALUES (1,'Ali',25),(2,'Sara',35),(3,'Omar',40);")
        con = sqlite3.connect(":memory:")
        try:
            con.executescript(schema)
            rows = con.execute(q).fetchall()
            rows = [r[0] for r in rows]
            return bool(rows == ["Sara", "Omar"]), str(rows)
        except Exception as e:
            return False, str(e)[:200]
        finally:
            con.close()
    if family == "R3":
        lines = [ln.strip().lower() for ln in (reply or "").strip().splitlines()
                 if ln.strip()]
        blob = " ".join(lines)
        checks = ["clone https://github.com/x/y.git" in blob,
                  any("checkout" in ln and "feat-z" in ln for ln in lines),
                  any(ln.startswith("git add") for ln in lines),
                  any("commit" in ln and "feat: z" in ln for ln in lines),
                  any("push" in ln and "origin" in ln and "feat-z" in ln
                      for ln in lines)]
        return bool(all(checks)), str(checks)
    if family == "R4":
        try:
            obj = extract_json_object(reply)
            d = json.loads(obj) if obj else {}
            ok = any("index.html" in json.dumps(r)
                     for r in d.get("rewrites", []))
        except Exception:
            ok = False
        return bool(ok), "vercel-rewrites-check"
    if family == "R5":
        code = extract_code(reply, "javascript") or extract_code(reply, "js")
        low = code.lower()
        checks = ["createclient" in low or "supabase" in low,
                  ".from('users')" in low or '.from("users")' in low,
                  "select" in low, "eq" in low and "active" in low,
                  "throw" in low or "error" in low,
                  "async" in low and "await" in low]
        return bool(all(checks)), str(checks)
    if family == "R6":
        if shutil.which("patch") is None:
            raise _MissingTool("patch binary not found")
        diff = extract_code(reply, "diff")
        root = sandbox.create_sandbox()
        try:
            target = os.path.join(root, "calc.py")
            with open(target, "w") as f:
                f.write(cases.R6_ORIG)
            diff = diff if diff.endswith("\n") else diff + "\n"
            dp = os.path.join(root, "c.diff")
            with open(dp, "w") as f:
                f.write(diff)
            strip = None
            for pflag in ("-p0", "-p1"):
                with open(dp) as f:
                    dry = subprocess.run(["patch", pflag, "--dry-run"],
                                         cwd=root, stdin=f,
                                         capture_output=True, text=True,
                                         timeout=30)
                if dry.returncode == 0:
                    strip = pflag
                    break
            if strip is None:
                return False, (dry.stdout + dry.stderr)[-300:]
            with open(dp) as f:
                subprocess.run(["patch", strip, "-s"], cwd=root, stdin=f,
                               capture_output=True, text=True, timeout=30)
            with open(target) as f:
                content = f.read()
            ok = "def sum_all" in content and "s += i" in content
            return ok, (dry.stdout + dry.stderr)[-300:]
        finally:
            sandbox.destroy_sandbox(root)
    if family == "R7":
        t = (reply or "").strip()
        ok = ("<tool_call>" in t and "</tool_call>" in t
              and "<function=calculator.add>" in t
              and re.search(r"<parameter=a>\s*17\s*</parameter>", t) is not None
              and re.search(r"<parameter=b>\s*25\s*</parameter>", t) is not None)
        return bool(ok), "toolcall-format-check"
    if family == "R8":
        line = (reply or "").strip().splitlines()[0].strip().strip("`") \
            if (reply or "").strip() else ""
        ok = (re.match(r"^(feat|fix|docs|refactor|test)(\(.+\))?: [a-z]",
                       line) is not None
              and not line.endswith(".") and len(line) <= 72
              and ("auth" in line or "rate" in line or "limit" in line))
        return bool(ok), line[:100]
    if family == "R9":
        low = (reply or "").lower()
        checks = ["<button" in low and "click me" in low, "<style" in low,
                  "flex" in low,
                  ("justify-content" in low and "align-items" in low)
                  or "margin: auto" in low or "place-items" in low,
                  "blue" in low or "#007bff" in low or "#0000ff" in low
                  or "rgb(0" in low]
        return bool(all(checks)), str(checks)
    if family == "R10":
        code = (extract_code(reply, "jsx") or extract_code(reply, "tsx")
                or extract_code(reply, "javascript"))
        checks = ["usestate" in code.lower(),
                  "usestate(0)" in code.replace(" ", ""),
                  "onclick" in code.lower(), "setcount" in code.lower(),
                  ("counter" in code)
                  and ("export default" in code or "export" in code)]
        return bool(all(checks)), str(checks)
    if family == "R11":
        code = extract_code(reply, "typescript") or extract_code(reply, "ts")
        tsc = shutil.which("tsc")
        if tsc is None:
            low = code.lower()
            ok = ("interface user" in low and "greet" in low
                  and ": string" in code)
            return ok, "tsc-missing-static"
        root = sandbox.create_sandbox()
        try:
            with open(os.path.join(root, "t.ts"), "w") as f:
                f.write(code + "\nconst _chk: string = "
                        "greet({name: \"Test\", age: 1});\n")
            c = subprocess.run([tsc, "--noEmit", "--strict",
                                os.path.join(root, "t.ts")],
                               capture_output=True, text=True, timeout=120)
            return c.returncode == 0, c.stderr[-400:] or "tsc-clean"
        finally:
            sandbox.destroy_sandbox(root)
    if family == "R12":
        if shutil.which("psql") is None:
            raise _MissingTool("psql binary not found")
        q = extract_code(reply, "sql").strip().rstrip(";")
        setup = ("DROP TABLE IF EXISTS products; CREATE TABLE products"
                 "(id SERIAL PRIMARY KEY, name TEXT, price NUMERIC); "
                 "INSERT INTO products(name,price) VALUES "
                 "('Keyboard',50),('Mouse',25),('Monitor',200); ")
        c = subprocess.run(["psql", "-h", "/tmp", "-p", "55433", "-d",
                            "postgres", "-tA", "-c", setup + " " + q],
                           capture_output=True, text=True, timeout=60)
        rows = [ln for ln in c.stdout.strip().splitlines() if ln.strip()]
        return bool(c.returncode == 0 and rows == ["Keyboard", "Mouse"]), \
            str(rows) + (c.stderr[-200:] if c.returncode else "")
    if family == "H1":
        return bool("126" in (reply or "")), "increasing-digits-check"
    if family == "H2":
        t = reply or ""
        ok = ("27" in t and "36" in t and "45" in t and "0" in t)
        return bool(ok), "diophantine-check"
    if family == "H3":
        clean = (reply or "").replace("*", "")
        m = re.findall(r"(?:remainder|answer|result|equals?|=)\s*:?\s*(\d+)",
                       clean, re.I)
        ok = (m and m[-1] == "4") or ("remainder is 4" in clean.lower())
        return bool(ok), "modexp-check"
    if family == "H4":
        code = extract_code(reply, "python")
        ok, log = _py_ok(
            code, "assert longest_pal('babad') in ('bab','aba') and "
                  "longest_pal('cbbd')=='bb' and longest_pal('a')=='a' and "
                  "longest_pal('ac') in ('a','c'); print('PAL_OK')", timeout=60)
        return bool(ok and "PAL_OK" in log), log
    if family == "H5":
        code = extract_code(reply, "python")
        ok, log = _py_ok(
            code, "import time; b=TokenBucket(rate=10, capacity=2); "
                  "assert b.allow() and b.allow() and not b.allow(); "
                  "w=b.wait_time(); assert 0 < w <= 0.2, w; time.sleep(0.25); "
                  "assert b.allow(); print('TB_OK')", timeout=60)
        return bool(ok and "TB_OK" in log), log
    if family == "H6":
        code = extract_code(reply, "python")
        ok, log = _py_ok(
            code, "assert first_occurrence([1,2,2,2,3],2)==1 "
                  "and first_occurrence([1,2,2,2,3],4)==-1 "
                  "and first_occurrence([2,2,2],2)==0 "
                  "and first_occurrence([],5)==-1; print('BS_OK')",
            timeout=60)
        return bool(ok and "BS_OK" in log), log
    raise KeyError("unknown code-bench-25 family: %r" % (family,))


class _MissingTool(RuntimeError):
    """Executor prerequisite missing (binary/service). Maps to ERROR."""


def _status_for(passed, error_kind):
    if error_kind == "timeout":
        return "TIMEOUT"
    if error_kind == "missing-tool":
        return "ERROR"
    return "PASS" if passed else "FAIL"


def _h3_manifest_sha():
    """SHA256 of the H3 Task DSL manifest (for dynamic attempt records)."""
    path = os.path.join(HERE, "manifests", "H3.json")
    with open(path, encoding="utf-8") as f:
        return sha256_manifest(json.load(f))


def _manifest_prompt(family):
    """Canonical prompt from the Task DSL manifest (Y-8 single source).

    Returns the manifest "prompt" string, or None when absent/unreadable
    (caller falls back to frozen cases.py — the Y-8 equality test guards
    that the two sources stay byte-identical).
    """
    path = os.path.join(HERE, "manifests", family + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        prompt = data.get("prompt")
        return prompt if isinstance(prompt, str) and prompt else None
    except Exception:
        return None


def prompt_messages(family):
    """Executor prompt source: manifest first, frozen cases as fallback.

    Y-8: manifests carry the byte-identical canonical prompt
    (tests/backends/test_manifest_truth.py guards equality), so the
    manifest becomes the single source of truth for easy R13/A16/S6
    additions. B58 hash inputs are unchanged (cases.prompt_text).
    """
    text = _manifest_prompt(family)
    if text is not None:
        return [{"role": "user", "content": text}]
    return cases.prompt_messages(family)


def _run_h3_dynamic(chat, run_id, model_id, trial_id, index, seed, variant):
    """H3.seed -> generated instance -> same-kind oracle. SPEC 9.

    Surface varies (numbers/names/representation/wording/context);
    truth is preserved (unique modular-equation solution).
    """
    inst = build_h3_equation(seed, variant=variant, index=index)
    messages = [{"role": "user", "content": inst["prompt"]}]
    opts = cases.chat_options("H3")
    text, secs, usage = "", 0.0, {}
    passed, log, error_kind, err_msg = False, "", None, None
    try:
        text, secs, usage = chat(messages, **opts)
        passed, log = check_h3_equation(text, inst["oracle"]["expected"])
    except sandbox.SandboxTimeout as e:
        error_kind, err_msg = "timeout", str(e)[:300]
        log = "TIMEOUT: %s" % err_msg
    except _MissingTool as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = "infra: %s" % err_msg
    except Exception as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = "executor-error: %s" % err_msg
    status = _status_for(passed, error_kind)
    attempt = {
        "run_id": run_id,
        "model_id": model_id,
        "task_family_id": "H3",
        "instance_id": inst["instance_id"],
        "variant_class": variant,
        "trial_id": trial_id,
        "primary_status": status,
        "score": 1.0 if status == "PASS" else 0.0,
        "eligible_for_task_score": status in ("PASS", "PARTIAL", "FAIL",
                                              "TIMEOUT", "INVALID"),
        "eligible_for_pass_rate": status in ("PASS", "PARTIAL", "FAIL",
                                             "TIMEOUT", "INVALID"),
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": False,
        "primary_failure": None if status == "PASS" else (
            "TIMEOUT" if status == "TIMEOUT"
            else ("HARNESS_ERROR" if status == "ERROR" else "WRONG_RESULT")),
        "secondary_failure_tags": [],
        "seed": seed,
        "reasoning_mode": reasoning_mode_for(opts.get("think"),
                                             opts.get("num_predict")),
        "secs": round(secs, 1) if isinstance(secs, (int, float)) else secs,
        "log": str(log)[-500:],
        "sample": (text or "")[:600],
        "prompt_sha256": sha256_bytes(inst["prompt"].encode("utf-8")),
        "manifest_sha256": _h3_manifest_sha(),
        "oracle_sha256": inst["oracle_hash"],
    }
    if err_msg:
        attempt["error"] = err_msg
    response = {"instance_id": inst["instance_id"], "trial_id": trial_id,
                "messages": messages, "options": opts, "reply": text,
                "usage": usage if isinstance(usage, dict) else {}}
    return validate_attempt(attempt), response


def run_family(family, chat, run_id, model_id, trial_id=1, index=1, seed=0,
               manifest=None, variant=None):
    """Run one canonical family with a chat callable.

    Returns (attempt_record, response_record). The attempt record is
    schema-valid per shared/schemas.py (C4/C83). No scoring.

    variant: None/"canonical" -> frozen PROMPT_PACK v1 prompt. H3 also
      serves "perturbed"/"novel" generated instances (same oracle kind:
      unique solution of a modular equation). Any other (family,
      variant) pair raises TypeError so the runner skips it (NA, DEN).
    """
    v = variant or "canonical"
    if v != "canonical":
        if family != "H3":
            raise TypeError("variant %r not supported for family %r"
                            % (v, family))
        return _run_h3_dynamic(chat, run_id, model_id, trial_id, index,
                               seed, v)
    messages = prompt_messages(family)
    opts = cases.chat_options(family)
    instance = instances.make_instance(
        family, cases.prompt_text(family), manifest or {},
        variant="canonical", index=index, seed=seed)
    text, secs, usage = "", 0.0, {}
    passed, log, error_kind, err_msg = False, "", None, None
    try:
        text, secs, usage = chat(messages, **opts)
        passed, log = check_family(family, text)
    except sandbox.SandboxTimeout as e:
        error_kind, err_msg = "timeout", str(e)[:300]
        log = "TIMEOUT: %s" % err_msg
    except _MissingTool as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = "infra: %s" % err_msg
    except Exception as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = "executor-error: %s" % err_msg
    status = _status_for(passed, error_kind)
    attempt = {
        "run_id": run_id,
        "model_id": model_id,
        "task_family_id": family,
        "instance_id": instance["instance_id"],
        "variant_class": "canonical",
        "trial_id": trial_id,
        "primary_status": status,
        "score": 1.0 if status == "PASS" else 0.0,
        "eligible_for_task_score": status in ("PASS", "PARTIAL", "FAIL",
                                              "TIMEOUT", "INVALID"),
        "eligible_for_pass_rate": status in ("PASS", "PARTIAL", "FAIL",
                                             "TIMEOUT", "INVALID"),
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": False,
        "primary_failure": None if status == "PASS" else (
            "TIMEOUT" if status == "TIMEOUT"
            else ("HARNESS_ERROR" if status == "ERROR" else "WRONG_RESULT")),
        "secondary_failure_tags": [],
        "seed": seed,
        "reasoning_mode": reasoning_mode_for(opts.get("think"),
                                             opts.get("num_predict")),
        "secs": round(secs, 1) if isinstance(secs, (int, float)) else secs,
        "log": str(log)[-500:],
        "sample": (text or "")[:600],
        "prompt_sha256": instance["prompt_sha256"],
        "manifest_sha256": instance["manifest_sha256"],
    }
    if err_msg:
        attempt["error"] = err_msg
    response = {"instance_id": instance["instance_id"], "trial_id": trial_id,
                "messages": messages, "options": opts, "reply": text,
                "usage": usage if isinstance(usage, dict) else {}}
    return validate_attempt(attempt), response


def prompt_pack_sha256():
    """SHA256 over all canonical prompts (for run manifest prompt_sha256)."""
    blob = "".join(cases.prompt_text(f) for f in cases.FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    """SHA256 of this executor file's bytes (for run manifest)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())


def write_raw_run(out_root, run_manifest, attempts, responses,
                  environment=None):
    """Write results/raw/RUN-ID/ layout (SPEC 33). Returns run dir path."""
    manifest = validate_run_manifest(run_manifest)
    run_id = manifest.get("run_id", run_manifest.get("run_id", "RUN"))
    rundir = os.path.join(out_root, run_id)
    os.makedirs(rundir, exist_ok=True)
    with open(os.path.join(rundir, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    with open(os.path.join(rundir, "events.jsonl"), "w",
              encoding="utf-8") as f:
        for a in attempts:
            f.write(json.dumps(validate_attempt(a), ensure_ascii=False)
                    + "\n")
    with open(os.path.join(rundir, "responses.jsonl"), "w",
              encoding="utf-8") as f:
        for r in responses:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    env = dict(environment or {})
    env.setdefault("written_utc",
                   datetime.datetime.now(datetime.timezone.utc).isoformat())
    with open(os.path.join(rundir, "environment.json"), "w",
              encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=1)
    return rundir
