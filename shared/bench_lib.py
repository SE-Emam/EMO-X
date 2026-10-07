"""EMO-X shared library (PROMPT_PACK v1).

chat() + extract_code() + all exec verifiers + result JSON writer.
Python stdlib only (urllib transport lives in backends.py).

Ported from /tmp/bench_df1.py, /tmp/bench_df2.py, /tmp/bench_df3.py
(do not re-run those files; this is the maintained copy).

Execution safety (PLAN §0.5): temporary working dirs, minimal child
environment, timeouts on subprocesses. This is not network isolation.
"""

import json
import os
import re

try:
    import sandbox
except ImportError:  # `python shared/run.py` vs package import
    from shared import sandbox

try:
    from backends import get_default_chat, make_chat
except ImportError:  # `python shared/run.py` vs package import
    try:
        from shared.backends import get_default_chat, make_chat
    except ImportError:
        get_default_chat = None
        make_chat = None

PROMPT_PACK = "v1"

_DEFAULT_CHAT = None


def configure(base_url=None, model=None, backend=None, api_key=None, chat_callable=None):
    """Set the module-level chat used by chat(). Returns the callable."""
    global _DEFAULT_CHAT
    if chat_callable is not None:
        _DEFAULT_CHAT = chat_callable
        return _DEFAULT_CHAT
    if make_chat is None:
        raise RuntimeError("backends module unavailable")
    _DEFAULT_CHAT = make_chat(
        backend or os.environ.get("BACKEND", "kaggle"), base_url, model, api_key
    )
    return _DEFAULT_CHAT


def chat(messages, temp=0.4, max_tokens=512, think=None, num_predict=None):
    """chat() interface: (text, secs, usage). Routes via backends.py.

    think/num_predict None -> OpenAI-compatible /chat/completions.
    Otherwise -> Ollama native /api/chat (think flag + num_predict).
    """
    global _DEFAULT_CHAT
    if _DEFAULT_CHAT is None:
        if get_default_chat is None:
            raise RuntimeError("no chat configured; call configure() first")
        _DEFAULT_CHAT = get_default_chat()
    return _DEFAULT_CHAT(
        messages, temp=temp, max_tokens=max_tokens, think=think, num_predict=num_predict
    )


def extract_code(text, lang=None):
    """First fenced block (optionally filtered by language), else raw text.

    Output is passed through strip_special_tokens() first: template/chat
    control tokens (e.g. <|im_end|>) are transport artifacts, never model
    content, and must not reach any checker.
    """
    text = strip_special_tokens(text)
    m = re.findall(r"```(\w*)\n(.*?)```", text or "", re.S)
    if m:
        if lang:
            for tag, code in m:
                if tag.lower() == lang:
                    return code
        return m[0][1]
    return (text or "").strip()


# ---------------- output hygiene (audit fix: special-token tails) ----------------

_SPECIAL_TOKEN_RE = re.compile(
    r"<\|(?:im_start|im_end|im_sep|endoftext|end_of_text|eot|eos|bos|pad|unk|mask|sep|cls)\|?>|"
    r"</s>|<s>",
)


def strip_special_tokens(text):
    """Remove chat/template control tokens from a model reply.

    Tokens like <|im_end|> are emitted by the serving template, not the
    model. Left in place they corrupt otherwise-correct answers: a clean
    TypeScript file fails tsc, a clean JSON object fails json.loads, a
    clean SQL query fails execution, a clean Rust program fails rustc.
    Returns "" for non-string input. Idempotent.
    """
    if not isinstance(text, str):
        return ""
    return _SPECIAL_TOKEN_RE.sub("", text)


def arabic_ratio(t):
    """Fraction of Arabic-block chars. T5 gate: pass iff ratio > 0.3."""
    t = t or ""
    ar = len(re.findall(r"[\u0600-\u06FF]", t))
    return ar / max(len(t), 1)


# --- P1 (PROMPT_PACK v2, 2026-10-07): Latin-language + semantic helpers ---
# Mirrors suites/code-bench-25/executor.py (kept local: this legacy module
# stays dependency-free). T9/T10 pair the language ratio with a semantic
# checklist; T5/T6 keep the legacy ratio plus an additive semantic signal.


def _word_ratio(t, markers):
    words = re.findall(r"[^\W\d_]+", (t or "").lower(), re.UNICODE)
    if not words:
        return 0.0
    return sum(1 for w in words if w in markers) / len(words)


SPANISH_MARKERS = frozenset(
    [
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "que",
        "qué",
        "es",
        "son",
        "está",
        "están",
        "en",
        "de",
        "del",
        "al",
        "con",
        "para",
        "por",
        "como",
        "cómo",
        "este",
        "esta",
        "estos",
        "estas",
        "ese",
        "esa",
        "pero",
        "porque",
        "también",
        "tambien",
        "hay",
        "tiene",
        "tienen",
        "puede",
        "función",
        "funcion",
        "código",
        "codigo",
        "ejemplo",
        "ámbito",
        "ambito",
        "alcance",
        "conserva",
        "recuerda",
        "mantiene",
        "explicación",
        "explicacion",
        "cierre",
        "donde",
        "exteriores",
        "interior",
        "exterior",
    ]
)

PORTUGUESE_MARKERS = frozenset(
    [
        "que",
        "uma",
        "um",
        "uns",
        "umas",
        "são",
        "sao",
        "está",
        "esta",
        "este",
        "estes",
        "em",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "no",
        "na",
        "com",
        "para",
        "por",
        "como",
        "mas",
        "porque",
        "também",
        "tambem",
        "há",
        "tem",
        "têm",
        "pode",
        "função",
        "funcao",
        "código",
        "codigo",
        "exemplo",
        "escopo",
        "mantém",
        "mantem",
        "conserva",
        "lembra",
        "explicação",
        "explicacao",
        "onde",
        "variáveis",
        "variaveis",
    ]
)


def spanish_ratio(t):
    """Fraction of Spanish-marker words. T9 gate: pass iff ratio > 0.10."""
    return _word_ratio(t, SPANISH_MARKERS)


def portuguese_ratio(t):
    """Fraction of Portuguese-marker words. T10 gate: pass iff ratio > 0.10."""
    return _word_ratio(t, PORTUGUESE_MARKERS)


def _fold_accents(t):
    import unicodedata

    t = (t or "").lower()
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def _all_groups_hit(t, groups):
    folded = _fold_accents(t)
    return [any(g in folded for g in group) for group in groups]


T9_SEMANTIC_GROUPS = (
    ("funcion",),
    ("ambito", "alcance"),
    ("conserv", "recuerd", "mantien"),
    ("ejemplo", "codigo"),
)

T10_SEMANTIC_GROUPS = (
    ("funcao",),
    ("escopo",),
    ("mant", "conserv", "lembr"),
    ("exemplo", "codigo"),
)

CLOSURE_SEMANTIC_MIN_HITS = 2


def closure_semantic_hits(t):
    folded = _fold_accents(t)
    low = (t or "").lower()
    n = sum(1 for m in ("function", "scope", "lexical", "closure") if m in folded)
    n += sum(1 for m in ("دالة", "نطاق", "مثال", "معجم") if m in low)
    return n


T6_SEMANTIC_GROUPS = (
    ("اجمع",),
    ("ترجع", "تجمع", "مجموع", "return", "جمع"),
    ("مثال", "شرح", "تأخذ", "تاخذ", "وسيط", "```"),
)


# ---------------- exec verifiers (all sandboxed, all with timeouts) ----------------


def _clean_env():
    """Use the canonical minimal environment for child processes.

    Keep this wrapper for legacy callers while sharing the current
    sandbox environment policy.
    """
    return sandbox._clean_env()


def run_py(code, test, timeout=30):
    """Append `test` to `code`, run with python3. Returns (ok, log_tail)."""
    return sandbox.run_python_code(code, test, timeout=timeout)


def run_py_file(code, timeout=30):
    """Run a full file content. Returns (ok, stdout, log_tail)."""
    rc, output = sandbox.run_in_sandbox(["python3", "-c", code], timeout=timeout)
    return rc == 0, output, output[-500:]


def run_js(code, test, timeout=30):
    """Append `test` to `code`, run with node. Returns (ok, log_tail)."""
    rc, output = sandbox.run_in_sandbox(["node", "-e", code + "\n" + test], timeout=timeout)
    return rc == 0, output[-500:]


def run_rust(code, timeout_compile=120, timeout_run=30):
    """Compile a complete Rust program with rustc, run it.

    Program must print its own _OK marker. Returns (ok, log_tail).
    """
    d = sandbox.create_sandbox()
    try:
        sandbox.write_sandbox_file(d, "t.rs", code)
        rc, output = sandbox.run_in_sandbox(
            ["rustc", "-O", "t.rs", "-o", "t"], sandbox_dir=d, timeout=timeout_compile
        )
        if rc != 0:
            return False, output[-400:]
        rc, output = sandbox.run_in_sandbox(["./t"], sandbox_dir=d, timeout=timeout_run)
        return rc == 0, output[-300:]
    finally:
        sandbox.destroy_sandbox(d)


def verify_tsc(code, extra='const _chk: string = greet({name: "Test", age: 1});', timeout=120):
    """Type-check TS with tsc --noEmit --strict. Returns (ok, log).

    The compiler runs in the networkless execution container.
    """
    d = sandbox.create_sandbox()
    try:
        sandbox.write_sandbox_file(d, "t.ts", code + "\n" + extra + "\n")
        rc, output = sandbox.run_in_sandbox(
            ["tsc", "--noEmit", "--strict", "t.ts"], sandbox_dir=d, timeout=timeout
        )
        return rc == 0, output[-400:] or "tsc-clean"
    finally:
        sandbox.destroy_sandbox(d)


def sqlite_query(query, schema, rows, timeout=30):
    """Run a SELECT against an in-memory sqlite3 DB. Returns (rows, error).

    schema: DDL string; rows: list of tuples to insert into the single table.
    Kept generic; callers build their own table (R2 fixture documented here).
    """
    import sqlite3

    _ = timeout  # sqlite in-memory exec is instant; kept for signature parity
    con = sqlite3.connect(":memory:")
    try:
        con.executescript(schema)
        return con.execute(query).fetchall(), None
    except Exception as e:
        return [], str(e)[:200]
    finally:
        con.close()


def psql_query(query, setup_sql, host="/tmp", port="55433", db="postgres", timeout=60):
    """Run query via local psql test instance. Returns (rows, returncode, err).

    Requires the scratch postgres on host:port (see code-bench-25/SKILL.md).
    Missing binary/instance -> (None, -1, message); caller marks test error,
    never a silent pass.
    """
    if host != "/tmp":
        raise ValueError("PostgreSQL checks are limited to the local socket")
    rc, output = sandbox.run_in_sandbox(
        [
            "psql",
            "-h",
            host,
            "-p",
            str(port),
            "-d",
            db,
            "-tA",
            "-c",
            setup_sql + " " + query,
        ],
        timeout=timeout,
    )
    rows = [line for line in output.splitlines() if line.strip() and not line.startswith("psql:")]
    err = "\n".join(line for line in output.splitlines() if line.startswith("psql:"))[-200:]
    return rows, rc, err


def verify_patch(orig_name, orig_content, diff_text, must_contain=(), timeout=30):
    """Dry-run a unified diff with `patch`, apply, check content.

    Returns (ok, log_tail). Corrected R6 check: patch must apply AND the
    patched file must contain every string in must_contain (e.g. the renamed
    symbol AND the preserved body) — an applying-but-wrong diff fails.
    """
    d = sandbox.create_sandbox()
    try:
        target = sandbox.write_sandbox_file(d, orig_name, orig_content)
        diff = diff_text if diff_text.endswith("\n") else diff_text + "\n"
        strip = None
        dry_output = ""
        for pflag in ("-p0", "-p1"):  # accept plain and git-style (a/ b/) headers
            dry_rc, dry_output = sandbox.run_in_sandbox(
                ["patch", pflag, "--dry-run"],
                sandbox_dir=d,
                timeout=timeout,
                input_text=diff,
            )
            if dry_rc == 0:
                strip = pflag
                break
        if strip is None:
            return False, dry_output[-300:]
        apply_rc, apply_output = sandbox.run_in_sandbox(
            ["patch", strip, "-s"], sandbox_dir=d, timeout=timeout, input_text=diff
        )
        if apply_rc != 0:
            return False, apply_output[-300:]
        with open(target) as f:
            content = f.read()
        ok = all(s in content for s in must_contain)
        return ok, dry_output[-300:]
    finally:
        sandbox.destroy_sandbox(d)


CALL_RE = re.compile(r"<tool_call>\s*<function=([\w]+)>\s*(.*?)</function>\s*</tool_call>", re.S)
PARAM_RE = re.compile(r"<parameter=([\w]+)>\s*(.*?)\s*</parameter>", re.S)


def parse_tool_call(text):
    """Parse one <tool_call> block. Returns (func, params) or (None, {}).

    Exact-parameter-names rule (the <parameter=P> lesson): the tag form is
    `<parameter=NAME>value</parameter>`. JSON-ish `<parameter name="N">`,
    bare `<N>`, or markdown variants do NOT parse and count as no-tool-call.
    """
    m = CALL_RE.search(text or "")
    if not m:
        return None, {}
    return m.group(1), dict(PARAM_RE.findall(m.group(2)))


# ---------------- result JSON writer ----------------


def load_results(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def save_result(path, name, record):
    """Merge one test record into the JSON file at path. Returns all results."""
    res = load_results(path)
    res[name] = record
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return res
