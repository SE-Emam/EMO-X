"""Executor glue for suites/code-bench-25 (stdlib only).

Runs canonical cases from cases.py inside shared/sandbox.py and emits
schema-valid raw attempt records (SPEC C4/C83 fields) under
results/raw/RUN-ID/. No scoring here (X-3 owns scoring).

Oracle logic mirrors the legacy checks in shared/run.py (frozen pass
criteria); only the execution substrate changed (bench_lib -> sandbox).

Import note (High H3 basename isolation): sibling cases.py /
instances.py are loaded by file path under unique module names
(code25_cases / code25_instances, aliased as cases / instances for
internal use) — never bare `import cases` — because every suite
ships a cases.py and bare imports collide in sys.modules when
several suites run in one process.

Usage:
  chat = <callable: (messages, temp=..., ...) -> (text, secs, usage)>
  rec = run_family("H3", chat, run_id="RUN-1", model_id="m", trial_id=1)
  write_raw_run(out_dir, run_manifest, attempts, responses)
"""

import datetime
import importlib.util
import json
import os
import re
import shlex
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import sandbox  # noqa: E402
from backends import reasoning_mode_for  # noqa: E402 (Y-5: attempt mode tag)
from manifests import sha256_bytes, sha256_manifest  # noqa: E402
from schemas import validate_attempt, validate_run_manifest  # noqa: E402


def _load_sibling(mod_name, filename):  # noqa: E402
    """Load a sibling module by file path (basename isolation, High H3).

    Unique mod_name (e.g. code25_cases) avoids sys.modules collisions
    with suites/security/cases.py; the caller aliases the result as
    `cases` / `instances` for internal compatibility.
    """
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    path = os.path.join(HERE, filename)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


cases = _load_sibling("code25_cases", "cases.py")  # noqa: E402
instances = _load_sibling("code25_instances", "instances.py")  # noqa: E402
try:
    from instance_factory import build_h3_equation, check_h3_equation
except ImportError:  # generators/ on path (runner) or add it (standalone)
    GEN = os.path.normpath(os.path.join(HERE, "..", "..", "generators"))
    if GEN not in sys.path:
        sys.path.insert(0, GEN)
    from instance_factory import build_h3_equation, check_h3_equation

#: Variant classes served by this executor (SPEC 9). Canonical prompts are
#: frozen (PROMPT_PACK v1); H3 additionally serves generated perturbed/novel
#: instances. The H3 dynamic oracle kind follows the manifest's
#: math_subtype field: "modular_exponentiation" (the frozen canonical
#: kind, remainder of c^t divided by m) selects the "exp" generator
#: subtype, while a missing field keeps the legacy "linear" equation
#: subtype for existing manifests (P0-08).
VARIANTS = ("canonical", "perturbed", "novel")

#: Manifest spelling selecting the exponentiation generator subtype.
H3_MATH_SUBTYPE_MODULAR_EXPONENTIATION = "modular_exponentiation"


def _validate_diff_paths(diff):
    """Reject patch diffs that escape the sandbox (audit H4).

    `patch` interprets ---/+++ headers as file paths; a model reply
    containing `../` or an absolute path would write outside `root`
    despite cwd confinement. Raises ValueError on refusal.
    """
    for line in (diff or "").splitlines():
        s = line.strip()
        if s.startswith(("--- ", "+++ ")):
            path = s[4:].strip().split()[0] if len(s) > 4 else ""
            low = path.lower()
            if (
                not path
                or ".." in path
                or path.startswith("/")
                or low.startswith("a/../")
                or low.startswith("b/../")
                or path.startswith("\\")
            ):
                raise ValueError(f"patch path escape refused: {path[:80]!r}")


#: Runner skips unsupported (family, variant) pairs via TypeError (DEN: a
#: missing variant observation is NA, never zero).

# --- small helpers copied in spirit from shared/bench_lib.py (frozen
# behavior; legacy file untouched). Kept local so this suite never
# imports the legacy CLI-entangled modules.

CODE_FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.S)
CALL_RE = re.compile(r"<tool_call>\s*<function=([\w.]+)>\s*(.*?)</function>\s*</tool_call>", re.S)
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
                    return text[start : i + 1]
    return None


def arabic_ratio(text):
    text = text or ""
    ar = len(re.findall(r"[\u0600-\u06FF]", text))
    return ar / max(len(text), 1)


# --- P1 (PROMPT_PACK v2, 2026-10-07): Latin-language + semantic oracles ---
# T5's bare arabic_ratio gate passes any Arabic-looking text (even off-topic),
# so T9/T10 pair the language ratio with a semantic checklist, and T5/T6 gain
# an additive semantic signal beside (never replacing) the legacy ratio.


def _word_ratio(text, markers):
    """Fraction of word tokens in `markers` (case-insensitive, word-level).

    Word-level (not char-level like arabic_ratio): Latin scripts share the
    same Unicode block, so the signal must come from distinctive function
    words / content words, not from the script itself.
    """
    words = re.findall(r"[^\W\d_]+", (text or "").lower(), re.UNICODE)
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in markers)
    return hits / len(words)


#: Distinctive Spanish function/content words (single letters excluded —
#: they collide with other languages; multi-char markers carry the signal).
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

#: Distinctive Portuguese words (1-char tokens deliberately excluded:
#: bare "o"/"a"/"e" occur in English prose and would inflate the ratio).
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


def spanish_ratio(text):
    """Fraction of Spanish-marker words. T9 gate: pass iff ratio > 0.10."""
    return _word_ratio(text, SPANISH_MARKERS)


def portuguese_ratio(text):
    """Fraction of Portuguese-marker words. T10 gate: pass iff ratio > 0.10."""
    return _word_ratio(text, PORTUGUESE_MARKERS)


def _fold_accents(text):
    """Lowercase + strip diacritics so función/funcion match alike."""
    import unicodedata

    text = (text or "").lower()
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _all_groups_hit(text, groups):
    """True iff every semantic group has >=1 hit (folded substring match)."""
    folded = _fold_accents(text)
    return [any(g in folded for g in group) for group in groups]


def _valid_vercel_spa_rewrite(reply):
    """Require a parsed Vercel catch-all rewrite to the SPA entry point."""
    try:
        obj = extract_json_object(reply)
        config = json.loads(obj) if obj else None
    except (TypeError, ValueError):
        return False
    if not isinstance(config, dict):
        return False
    rewrites = config.get("rewrites")
    if not isinstance(rewrites, list):
        return False
    catch_all_sources = {"/(.*)", "/:path*"}
    return any(
        isinstance(rule, dict)
        and rule.get("source") in catch_all_sources
        and rule.get("destination") == "/index.html"
        for rule in rewrites
    )


def _dockerfile_instructions(text):
    """Parse the Dockerfile instruction subset needed by the R13 oracle."""
    known = {
        "ADD",
        "ARG",
        "CMD",
        "COPY",
        "ENTRYPOINT",
        "ENV",
        "EXPOSE",
        "FROM",
        "HEALTHCHECK",
        "LABEL",
        "MAINTAINER",
        "ONBUILD",
        "RUN",
        "SHELL",
        "STOPSIGNAL",
        "USER",
        "VOLUME",
        "WORKDIR",
    }
    instructions = []
    pending = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line and not pending:
            continue
        if line.startswith("#") and not pending:
            continue
        if line.endswith("\\"):
            pending += line[:-1].strip() + " "
            continue
        logical_line = pending + line
        pending = ""
        try:
            tokens = shlex.split(logical_line, comments=True, posix=True)
        except ValueError:
            return None
        if not tokens:
            continue
        instruction = tokens[0].upper()
        if instruction not in known:
            return None
        argument_text = logical_line.split(None, 1)[1] if len(tokens) > 1 else ""
        args = tokens[1:]
        if argument_text.startswith("[") and instruction in {
            "ADD",
            "CMD",
            "COPY",
            "ENTRYPOINT",
            "RUN",
        }:
            try:
                json_args = json.loads(argument_text)
            except ValueError:
                return None
            if not isinstance(json_args, list) or not all(
                isinstance(arg, str) for arg in json_args
            ):
                return None
            args = json_args
        instructions.append((instruction, args))
    if pending:
        return None
    saw_from = False
    for instruction, _ in instructions:
        if instruction == "FROM":
            saw_from = True
        elif not saw_from and instruction != "ARG":
            return None
    return instructions


def _dockerfile_has_required_python_app(text):
    """Validate R13's required Dockerfile directives and their arguments."""
    instructions = _dockerfile_instructions(text)
    if not instructions:
        return False
    bases = []
    workdirs = []
    copies = []
    installs = []
    commands = []
    for instruction, args in instructions:
        if instruction == "FROM":
            image = None
            skip_value = False
            for arg in args:
                if skip_value:
                    skip_value = False
                    continue
                if arg == "--platform":
                    skip_value = True
                elif arg.startswith("--platform="):
                    continue
                elif not arg.startswith("--"):
                    image = arg
                    break
            if image is None:
                return False
            bases.append(image.lower())
        elif instruction == "WORKDIR" and args:
            workdirs.append(args[0])
        elif instruction == "COPY":
            copy_args = [arg for arg in args if not arg.startswith("--")]
            if len(copy_args) >= 2:
                copies.append(copy_args[:-1])
        elif instruction == "RUN":
            normalized = [arg.strip("[]\",'").lower() for arg in args]
            if (
                len(normalized) >= 2
                and normalized[0] in ("pip", "pip3")
                and normalized[1] == "install"
            ) or (
                len(normalized) >= 4
                and normalized[0] in ("python", "python3")
                and normalized[1:4] == ["-m", "pip", "install"]
            ):
                installs.append(args)
        elif instruction == "CMD" and any(arg.strip() for arg in args):
            commands.append(args)
    return bool(
        bases
        and bases[-1] == "python:3.12-slim"
        and all(base.split("@", 1)[0].rsplit(":", 1)[-1] != "latest" for base in bases)
        and workdirs
        and workdirs[-1] == "/app"
        and any(
            any(os.path.basename(source) == "requirements.txt" for source in sources)
            for sources in copies
        )
        and installs
        and commands
    )


#: T9 semantic checklist (all four groups required): función/closure +
#: ámbito/entorno/contexto + conserva/captura + ejemplo/código.
#: Calibrated 2026-10-07 on t9_calibration.json (8 pos + 8 neg): G1 adds
#: closure/clausura; G2 adds entorno/contexto/lexico/scope/exterior-family/
#: bloque/anidada/padre/madre (real answers say "entorno", "función
#: padre/madre/hija", "alcance de bloque"); G3 adds captur/guard/acced/
#: persist/viv/cierr/atrap (real defs "captura", "guarda", "accede",
#: "sigue viva"); G4 adds code/prose illustration signals (bare var/let
#: excluded: "var" is a substring of "variables" and would pass incompletes).
T9_SEMANTIC_GROUPS = (
    ("funcion", "closure", "clausura"),
    (
        "ambito",
        "alcance",
        "entorno",
        "contexto",
        "lexico",
        "scope",
        "exterior",
        "interior",
        "externa",
        "externo",
        "interna",
        "interno",
        "bloque",
        "anidada",
        "padre",
        "madre",
    ),
    (
        "conserv",
        "recuerd",
        "mantien",
        "captur",
        "guard",
        "acced",
        "persist",
        "viv",
        "cierr",
        "atrap",
    ),
    (
        "ejemplo",
        "codigo",
        "function",
        "return",
        "console",
        "=>",
        "```",
        "mira",
        "supon",
        "imagin",
        "ilustr",
    ),
)

#: T10 semantic checklist: função + escopo + mantém + exemplo/código.
T10_SEMANTIC_GROUPS = (
    ("funcao",),
    ("escopo",),
    ("mant", "conserv", "lembr"),
    ("exemplo", "codigo"),
)

#: T5 additive semantic signal: closure-explanation keywords. At least
#: CLOSURE_SEMANTIC_MIN_HITS must appear beside the legacy arabic_ratio
#: gate (which is kept unchanged).
CLOSURE_SEMANTIC_MARKERS = (
    "function",
    "scope",
    "lexical",
    "closure",
    "دالة",
    "نطاق",
    "مثال",
    "معجم",
)
CLOSURE_SEMANTIC_MIN_HITS = 2


def closure_semantic_hits(text):
    """Count of closure keyword hits (folded, case-insensitive)."""
    folded = _fold_accents(text)
    low = (text or "").lower()
    n = sum(1 for m in ("function", "scope", "lexical", "closure") if m in folded)
    n += sum(1 for m in ("دالة", "نطاق", "مثال", "معجم") if m in low)
    return n


#: T6 additive semantic signal: the Arabic explanation must reference the
#: defined function and describe/illustrate it (kept lenient: code fence or
#: explanation verbs count as the illustration hit).
T6_SEMANTIC_GROUPS = (
    ("اجمع",),
    ("ترجع", "تجمع", "مجموع", "return", "جمع"),
    ("مثال", "شرح", "تأخذ", "تاخذ", "وسيط", "```"),
)


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
        return False, f"executor-error: {str(e)[:200]}"


def check_family(family, reply):
    """Run the family's canonical oracle. Returns (passed, log).

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
        ok, log = _py_ok(code, "assert fib(0)==0 and fib(1)==1 and fib(10)==55; print('FIB_OK')")
        return bool(ok and "FIB_OK" in log), log
    if family == "T3":
        code = extract_code(reply, "python")
        ok, log = _py_ok(code, "assert is_even(4)==True and is_even(5)==False; print('FIX_OK')")
        return bool(ok and "FIX_OK" in log), log
    if family == "T30":
        code = extract_code(reply, "python")
        test = (
            "import sqlite3\n"
            "db=sqlite3.connect(':memory:')\n"
            "db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, role TEXT)')\n"
            "db.executemany('INSERT INTO users(username,role) VALUES (?,?)', "
            "[('alice','user'),('bob','admin')])\n"
            "assert get_user('alice') == [(1,'alice','user')]\n"
            "try:\n"
            "    injected=get_user(\"' OR '1'='1\")\n"
            "except Exception:\n"
            "    injected=[]\n"
            "assert injected == []\n"
            "try:\n"
            '    get_user("\'; DROP TABLE users; --")\n'
            "except Exception:\n"
            "    pass\n"
            "assert db.execute('SELECT COUNT(*) FROM users').fetchone() == (2,)\n"
            "assert db.execute(\"SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='users'\").fetchone() == ('users',)\n"
            "print('T30_OK')"
        )
        ok, log = _py_ok(code, test, timeout=30)
        return bool(ok and "T30_OK" in log), log
    if family == "T33":
        code = extract_code(reply, "python")
        test = (
            "class _Response:\n"
            "    def __init__(self,status,payload=None):\n"
            "        self.status_code=status; self.payload=payload\n"
            "    def json(self): return self.payload\n"
            "class _Transport:\n"
            "    def __init__(self,responses): self.responses=iter(responses); self.calls=[]\n"
            "    def get(self,url): self.calls.append(url); return next(self.responses)\n"
            "delays=[]\n"
            "transport=_Transport([_Response(503),_Response(200,{'value':7})])\n"
            "result=fetch_json('https://mock.invalid/data',transport,delays.append)\n"
            "assert result == {'ok':True,'data':{'value':7},'attempt_count':2,"
            "'last_error':None}, result\n"
            "assert transport.calls == ['https://mock.invalid/data']*2\n"
            "assert delays == [0.1], delays\n"
            "permanent=_Transport([_Response(404)])\n"
            "delays=[]\n"
            "result=fetch_json('https://mock.invalid/missing',permanent,delays.append)\n"
            "assert result == {'ok':False,'data':None,'attempt_count':1,"
            "'last_error':'HTTP 404'}, result\n"
            "assert len(permanent.calls)==1 and delays==[]\n"
            "print('T33_OK')"
        )
        ok, log = _py_ok(code, test, timeout=30)
        return bool(ok and "T33_OK" in log), log
    if family == "T36":
        code = extract_code(reply, "python")
        test = (
            "import sqlite3\n"
            "connection=sqlite3.connect(':memory:')\n"
            "connection.execute('CREATE TABLE accounts(id INTEGER PRIMARY KEY, name TEXT)')\n"
            "connection.executemany('INSERT INTO accounts(id,name) VALUES (?,?)', "
            "[(1,'Ada'),(2,'Lin')])\n"
            "connection.commit()\n"
            "rows=migrate_and_query(connection)\n"
            "column=next(c for c in connection.execute('PRAGMA table_info(accounts)') "
            "if c[1]=='status')\n"
            "assert column[2].upper()=='TEXT' and column[3]==1 and "
            "column[4].strip(\"'\")=='active', column\n"
            "assert connection.execute('SELECT id,name FROM accounts ORDER BY id')"
            ".fetchall()==[(1,'Ada'),(2,'Lin')]\n"
            "assert rows==[(1,'Ada'),(2,'Lin')], rows\n"
            "print('T36_OK')"
        )
        ok, log = _py_ok(code, test, timeout=30)
        return bool(ok and "T36_OK" in log), log
    if family == "T4":
        code = extract_code(reply, "javascript") or extract_code(reply, "js")
        rc, log = sandbox.run_in_sandbox(
            [
                "node",
                "-e",
                code + "\nif (sumArr([1,2,3,4])!==10) throw new Error('bad'); console.log('JS_OK')",
            ],
            timeout=30,
        )
        return bool(rc == 0 and "JS_OK" in log), log
    if family == "T5":
        r = arabic_ratio(reply)
        sem = closure_semantic_hits(reply)
        ok = bool(r > 0.3 and sem >= CLOSURE_SEMANTIC_MIN_HITS)
        return ok, "arabic_ratio=%.3f closure_hits=%d/>=%d" % (
            r,
            sem,
            CLOSURE_SEMANTIC_MIN_HITS,
        )
    if family == "T6":
        code = extract_code(reply, "python")
        ok, log = _py_ok(code, "assert اجمع(2,3)==5; print('ARCODE_OK')")
        r = arabic_ratio(reply)
        sem = _all_groups_hit(reply, T6_SEMANTIC_GROUPS)
        ok = bool(ok and "ARCODE_OK" in log and r > 0.1 and all(sem))
        return ok, f"{log} arabic_ratio={r:.3f} sem={sem}"
    if family == "T9":
        r = spanish_ratio(reply)
        sem = _all_groups_hit(reply, T9_SEMANTIC_GROUPS)
        ok = bool(r > 0.10 and all(sem))
        return ok, f"spanish_ratio={r:.3f} sem={sem}"
    if family == "T10":
        r = portuguese_ratio(reply)
        sem = _all_groups_hit(reply, T10_SEMANTIC_GROUPS)
        ok = bool(r > 0.10 and all(sem))
        return ok, f"portuguese_ratio={r:.3f} sem={sem}"
    if family == "T7":
        try:
            obj = extract_json_object(reply)
            d = json.loads(obj) if obj else None
            ok = (
                d is not None
                and set(d) == {"name", "languages", "years"}
                and len(d["languages"]) == 3
                and isinstance(d["years"], int)
            )
        except Exception:
            ok = False
        return bool(ok), "json-struct-check"
    if family == "T8":
        code = extract_code(reply)
        root = sandbox.create_sandbox()
        try:
            # Generated code runs only in the networkless Docker sandbox.
            rc, out = sandbox.run_in_sandbox(["python3", "-c", code], sandbox_dir=root, timeout=30)
            lines = [ln for ln in out.strip().splitlines() if ln.strip()]
            ok = rc == 0 and bool(lines) and lines[-1].strip() == "5"
            return ok, out[-500:]
        except sandbox.SandboxTimeout as e:
            return False, str(e)[:500]
        finally:
            sandbox.destroy_sandbox(root)
    if family == "R1":
        code = extract_code(reply, "rust")
        root = sandbox.create_sandbox()
        try:
            sandbox.write_sandbox_file(root, "t.rs", code)
            rc, clog = sandbox.run_in_sandbox(
                ["rustc", "-O", "t.rs", "-o", "t"], sandbox_dir=root, timeout=120
            )
            if rc != 0:
                return False, clog[-400:]
            try:
                rc, log = sandbox.run_in_sandbox(["./t"], sandbox_dir=root, timeout=30)
            except sandbox.SandboxTimeout as e:
                return False, str(e)[:300]
            log = log[-300:]
            return bool(rc == 0 and "PRIME_OK" in log), log
        finally:
            sandbox.destroy_sandbox(root)
    if family == "R2":
        q = extract_code(reply, "sql").strip().rstrip(";")
        schema = (
            "CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, age INTEGER);"
            "INSERT INTO users VALUES (1,'Ali',25),(2,'Sara',35),(3,'Omar',40);"
        )
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
        lines = [ln.strip().lower() for ln in (reply or "").strip().splitlines() if ln.strip()]
        blob = " ".join(lines)
        checks = [
            "clone https://github.com/x/y.git" in blob,
            any("checkout" in ln and "feat-z" in ln for ln in lines),
            any(ln.startswith("git add") for ln in lines),
            any("commit" in ln and "feat: z" in ln for ln in lines),
            any("push" in ln and "origin" in ln and "feat-z" in ln for ln in lines),
        ]
        return bool(all(checks)), str(checks)
    if family == "R4":
        ok = _valid_vercel_spa_rewrite(reply)
        return ok, "vercel-catch-all-rewrite-check"
    if family == "R5":
        code = extract_code(reply, "javascript") or extract_code(reply, "js")
        low = code.lower()
        checks = [
            "createclient" in low or "supabase" in low,
            ".from('users')" in low or '.from("users")' in low,
            "select" in low,
            "eq" in low and "active" in low,
            "throw" in low or "error" in low,
            "async" in low and "await" in low,
        ]
        return bool(all(checks)), str(checks)
    if family == "R6":
        diff = extract_code(reply, "diff")
        try:
            _validate_diff_paths(diff)  # audit H4: refuse path escape
        except ValueError as e:
            return False, f"REFUSED: {str(e)[:200]}"
        root = sandbox.create_sandbox()
        try:
            target = sandbox.write_sandbox_file(root, "calc.py", cases.R6_ORIG)
            diff = diff if diff.endswith("\n") else diff + "\n"
            strip = None
            dry_output = ""
            for pflag in ("-p0", "-p1"):
                dry_rc, dry_output = sandbox.run_in_sandbox(
                    ["patch", pflag, "--dry-run"],
                    sandbox_dir=root,
                    timeout=30,
                    input_text=diff,
                )
                if dry_rc == 0:
                    strip = pflag
                    break
            if strip is None:
                return False, dry_output[-300:]
            apply_rc, apply_output = sandbox.run_in_sandbox(
                ["patch", strip, "-s"], sandbox_dir=root, timeout=30, input_text=diff
            )
            if apply_rc != 0:
                return False, apply_output[-300:]
            with open(target) as f:
                content = f.read()
            ok = "def sum_all" in content and "s += i" in content
            return ok, dry_output[-300:]
        finally:
            sandbox.destroy_sandbox(root)
    if family == "R7":
        t = (reply or "").strip()
        ok = (
            "<tool_call>" in t
            and "</tool_call>" in t
            and "<function=calculator.add>" in t
            and re.search(r"<parameter=a>\s*17\s*</parameter>", t) is not None
            and re.search(r"<parameter=b>\s*25\s*</parameter>", t) is not None
        )
        return bool(ok), "toolcall-format-check"
    if family == "R8":
        line = (
            (reply or "").strip().splitlines()[0].strip().strip("`")
            if (reply or "").strip()
            else ""
        )
        ok = (
            re.match(r"^(feat|fix|docs|refactor|test)(\(.+\))?: [a-z]", line) is not None
            and not line.endswith(".")
            and len(line) <= 72
            and ("auth" in line or "rate" in line or "limit" in line)
        )
        return bool(ok), line[:100]
    if family == "R9":
        low = (reply or "").lower()
        checks = [
            "<button" in low and "click me" in low,
            "<style" in low,
            "flex" in low,
            ("justify-content" in low and "align-items" in low)
            or "margin: auto" in low
            or "place-items" in low,
            "blue" in low or "#007bff" in low or "#0000ff" in low or "rgb(0" in low,
        ]
        return bool(all(checks)), str(checks)
    if family == "R10":
        code = (
            extract_code(reply, "jsx")
            or extract_code(reply, "tsx")
            or extract_code(reply, "javascript")
        )
        normalized = code.lower().replace(" ", "")
        checks = [
            "usestate" in normalized,
            "usestate(0)" in normalized,
            "onclick" in normalized,
            "setcount" in normalized,
            ("counter" in normalized) and ("exportdefault" in normalized or "export" in normalized),
        ]
        return bool(all(checks)), str(checks)
    if family == "R11":
        code = extract_code(reply, "typescript") or extract_code(reply, "ts")
        root = sandbox.create_sandbox()
        try:
            sandbox.write_sandbox_file(
                root,
                "t.ts",
                code + '\nconst _chk: string = greet({name: "Test", age: 1});\n',
            )
            rc, output = sandbox.run_in_sandbox(
                ["tsc", "--noEmit", "--strict", "t.ts"], sandbox_dir=root, timeout=120
            )
            return rc == 0, output[-400:] or "tsc-clean"
        finally:
            sandbox.destroy_sandbox(root)
    if family == "R12":
        q = extract_code(reply, "sql").strip().rstrip(";")
        setup = (
            "DROP TABLE IF EXISTS products; CREATE TABLE products"
            "(id SERIAL PRIMARY KEY, name TEXT, price NUMERIC); "
            "INSERT INTO products(name,price) VALUES "
            "('Keyboard',50),('Mouse',25),('Monitor',200); "
        )
        rc, output = sandbox.run_in_sandbox(
            [
                "psql",
                "-h",
                "/tmp",
                "-p",
                "55433",
                "-d",
                "postgres",
                "-tA",
                "-c",
                setup + " " + q,
            ],
            timeout=60,
        )
        rows = [
            line
            for line in output.strip().splitlines()
            if line.strip() and not line.startswith("psql:")
        ]
        return bool(rc == 0 and rows == ["Keyboard", "Mouse"]), str(rows) + (
            output[-200:] if rc else ""
        )
    if family == "R13":
        ok = _dockerfile_has_required_python_app(reply or "")
        return ok, f"dockerfile-structure-check={ok}"
    if family == "H1":
        return bool("126" in (reply or "")), "increasing-digits-check"
    if family == "H2":
        t = reply or ""
        ok = "27" in t and "36" in t and "45" in t and "0" in t
        return bool(ok), "diophantine-check"
    if family == "H3":
        clean = (reply or "").replace("*", "")
        m = re.findall(r"(?:remainder|answer|result|equals?|=)\s*:?\s*(\d+)", clean, re.I)
        ok = (m and m[-1] == "4") or ("remainder is 4" in clean.lower())
        return bool(ok), "modexp-check"
    if family == "H4":
        code = extract_code(reply, "python")
        ok, log = _py_ok(
            code,
            "assert longest_pal('babad') in ('bab','aba') and "
            "longest_pal('cbbd')=='bb' and longest_pal('a')=='a' and "
            "longest_pal('ac') in ('a','c'); print('PAL_OK')",
            timeout=60,
        )
        return bool(ok and "PAL_OK" in log), log
    if family == "H5":
        code = extract_code(reply, "python")
        ok, log = _py_ok(
            code,
            "import time; b=TokenBucket(rate=10, capacity=2); "
            "assert b.allow() and b.allow() and not b.allow(); "
            "w=b.wait_time(); assert 0 < w <= 0.2, w; time.sleep(0.25); "
            "assert b.allow(); print('TB_OK')",
            timeout=60,
        )
        return bool(ok and "TB_OK" in log), log
    if family == "H6":
        code = extract_code(reply, "python")
        ok, log = _py_ok(
            code,
            "assert first_occurrence([1,2,2,2,3],2)==1 "
            "and first_occurrence([1,2,2,2,3],4)==-1 "
            "and first_occurrence([2,2,2],2)==0 "
            "and first_occurrence([],5)==-1; print('BS_OK')",
            timeout=60,
        )
        return bool(ok and "BS_OK" in log), log
    if family == "A16":
        # P2 (PROMPT_PACK v2): real executive oracle via sandbox (like T6).
        # Static shape (asyncio.gather + fetch(1)/fetch(2)) AND runtime
        # result asyncio.run(fetch_all()) == [2, 4] must both hold.
        code = extract_code(reply, "python")
        has_gather = "asyncio.gather" in code
        has_calls = "fetch(1)" in code and "fetch(2)" in code
        ok, log = _py_ok(
            code,
            "import asyncio; assert asyncio.run(fetch_all())==[2,4]; print('ASYNC_OK')",
            timeout=30,
        )
        passed = bool(has_gather and has_calls and ok and "ASYNC_OK" in log)
        return passed, f"gather={has_gather} calls={has_calls} {log}"
    raise KeyError(f"unknown code-bench-25 family: {family!r}")


def check_variant(family, variant, reply):
    """Run a declared fixed variant through the same fail-closed sandbox."""
    if variant != "perturbed":
        raise KeyError(f"unsupported code-bench-25 variant: {family}/{variant}")
    if family == "T2":
        code = extract_code(reply, "python")
        test = (
            "assert fib(0)==0 and fib(1)==1\n"
            "expected_a,expected_b=0,1\n"
            "for _ in range(500): expected_a,expected_b=expected_b,expected_a+expected_b\n"
            "assert fib(500)==expected_a\n"
            "try: fib(-1)\n"
            "except ValueError: pass\n"
            "else: raise AssertionError('negative n must raise ValueError')\n"
            "try: fib(1.5)\n"
            "except TypeError: pass\n"
            "else: raise AssertionError('non-integer n must raise TypeError')\n"
            "print('T2_VARIANT_OK')"
        )
        ok, log = _py_ok(code, test, timeout=30)
        return bool(ok and "T2_VARIANT_OK" in log), log
    if family == "T3":
        code = extract_code(reply, "python")
        test = (
            "assert safe_average([1,2])==1.5\n"
            "assert safe_average([-2,1,4])==1.0\n"
            "assert safe_average([])==0\n"
            "print('T3_VARIANT_OK')"
        )
        ok, log = _py_ok(code, test, timeout=30)
        return bool(ok and "T3_VARIANT_OK" in log), log
    if family == "R2":
        query = extract_code(reply, "sql").strip().rstrip(";")
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(
                "CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT);"
                "CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,amount INTEGER);"
                "INSERT INTO users VALUES (1,'Ali'),(2,'Sara'),(3,'Omar');"
                "INSERT INTO orders VALUES "
                "(1,1,50),(2,1,60),(3,2,NULL),(4,3,110),(5,3,110);"
            )
            rows = connection.execute(query).fetchall()
            expected = [("Omar", 110), ("Omar", 110)]
            return rows == expected, repr(rows)
        except sqlite3.Error as error:
            return False, str(error)[:200]
        finally:
            connection.close()
    if family == "R5":
        code = extract_code(reply, "javascript") or extract_code(reply, "js")
        harness = (
            "\nconst assert = require('node:assert/strict');\n"
            "function mockClient(data,error){\n"
            "  const trace={};\n"
            "  const query={\n"
            "    select(columns){trace.select=columns;return this;},\n"
            "    eq(field,value){trace.eq=[field,value];return this;},\n"
            "    range(start,end){trace.range=[start,end];return this;},\n"
            "    then(resolve,reject){return Promise.resolve({data,error}).then(resolve,reject);}\n"
            "  };\n"
            "  return {trace,client:{from(table){trace.table=table;return query;}}};\n"
            "}\n"
            "(async()=>{\n"
            " const rows=[{id:3,name:'Omar'}];\n"
            " const success=mockClient(rows,null);\n"
            " assert.deepEqual(await getActiveUsers(success.client,2,2),rows);\n"
            " assert.deepEqual(success.trace,{table:'users',select:'id,name',"
            "eq:['active',true],range:[2,3]});\n"
            " const problem=new Error('temporary failure');\n"
            " const failure=mockClient(null,problem);\n"
            " let caught;\n"
            " try { await getActiveUsers(failure.client,1,2); } catch(error) { caught=error; }\n"
            " assert.equal(caught && caught.message,'temporary failure');\n"
            " console.log('R5_VARIANT_OK');\n"
            "})().catch(error=>{console.error(error);process.exit(1);});\n"
        )
        rc, log = sandbox.run_in_sandbox(["node", "-e", code + harness], timeout=30)
        return bool(rc == 0 and "R5_VARIANT_OK" in log), log[-400:]
    raise KeyError(f"no perturbed code-bench-25 variant for family: {family!r}")


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


def _h3_math_subtype(variant, manifest=None):
    """Resolve the H3 generator math subtype for a variant. SPEC 9.

    Precedence: an explicitly passed manifest dict's math_subtype field
    first, else the suite H3.json math_subtype field, else "linear".
    "modular_exponentiation" (the frozen canonical oracle kind) maps to
    the "exp" generator subtype; a missing field preserves the legacy
    "linear" equation subtype for existing manifests (P0-08).
    """
    data = manifest if isinstance(manifest, dict) else None
    if data is None:
        try:
            path = os.path.join(HERE, "manifests", "H3.json")
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return "linear"
    field = data.get("math_subtype")
    if not isinstance(field, dict):
        return "linear"
    if field.get(variant) == H3_MATH_SUBTYPE_MODULAR_EXPONENTIATION:
        return "exp"
    return "linear"


def _run_h3_dynamic(chat, run_id, model_id, trial_id, index, seed, variant, subtype="linear"):
    """H3.seed -> generated instance -> same-kind oracle. SPEC 9.

    Surface varies (numbers/names/representation/wording/context);
    truth is preserved (unique modular-equation solution for "linear",
    modular-exponentiation remainder for "exp" — the frozen canonical
    oracle kind selected via the manifest math_subtype field).
    """
    inst = build_h3_equation(seed, variant=variant, index=index, subtype=subtype)
    messages = [{"role": "user", "content": inst["prompt"]}]
    opts = cases.chat_options("H3")
    text, secs, usage = "", 0.0, {}
    passed, log, error_kind, err_msg = False, "", None, None
    try:
        text, secs, usage = chat(messages, **opts)
        passed, log = check_h3_equation(text, inst["oracle"]["expected"], subtype=subtype)
    except sandbox.SandboxTimeout as e:
        error_kind, err_msg = "timeout", str(e)[:300]
        log = f"TIMEOUT: {err_msg}"
    except _MissingTool as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = f"infra: {err_msg}"
    except Exception as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = f"executor-error: {err_msg}"
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
        "eligible_for_task_score": status in ("PASS", "PARTIAL", "FAIL", "TIMEOUT", "INVALID"),
        "eligible_for_pass_rate": status in ("PASS", "PARTIAL", "FAIL", "TIMEOUT", "INVALID"),
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": False,
        "primary_failure": None
        if status == "PASS"
        else (
            "TIMEOUT"
            if status == "TIMEOUT"
            else ("HARNESS_ERROR" if status == "ERROR" else "WRONG_RESULT")
        ),
        "secondary_failure_tags": [],
        "seed": seed,
        "reasoning_mode": reasoning_mode_for(opts.get("think"), opts.get("num_predict")),
        "secs": round(secs, 1) if isinstance(secs, (int, float)) else secs,
        "log": str(log)[-500:],
        "sample": (text or "")[:600],
        "prompt_sha256": sha256_bytes(inst["prompt"].encode("utf-8")),
        "manifest_sha256": _h3_manifest_sha(),
        "oracle_sha256": inst["oracle_hash"],
    }
    if err_msg:
        attempt["error"] = err_msg
    response = {
        "instance_id": inst["instance_id"],
        "trial_id": trial_id,
        "messages": messages,
        "options": opts,
        "reply": text,
        "usage": usage if isinstance(usage, dict) else {},
    }
    return validate_attempt(attempt), response


def run_family(
    family,
    chat,
    run_id,
    model_id,
    trial_id=1,
    index=1,
    seed=0,
    manifest=None,
    variant=None,
    subtype=None,
):
    """Run one canonical family with a chat callable.

    Returns (attempt_record, response_record). The attempt record is
    schema-valid per shared/schemas.py (C4/C83). No scoring.

    variant: None/"canonical" -> canonical prompt. H3 also serves generated
      "perturbed"/"novel" instances; T2, T3, R2, and R5 have fixed
      "perturbed" prompts and oracles. subtype is used only by H3. Any other
      (family, variant) pair raises TypeError so the runner skips it (NA, DEN).
    """
    v = variant or "canonical"
    if v != "canonical":
        if family == "H3":
            sub = subtype or _h3_math_subtype(v, manifest)
            return _run_h3_dynamic(chat, run_id, model_id, trial_id, index, seed, v, sub)
        try:
            prompt = cases.variant_prompt(family, v)
        except KeyError:
            raise TypeError(f"variant {v!r} not supported for family {family!r}")
        messages = [{"role": "user", "content": prompt}]
    else:
        prompt = cases.prompt_text(family)
        messages = prompt_messages(family)
    opts = cases.chat_options(family)
    instance = instances.make_instance(
        family,
        prompt,
        manifest or {},
        variant=v,
        index=index,
        seed=seed,
    )
    text, secs, usage = "", 0.0, {}
    passed, log, error_kind, err_msg = False, "", None, None
    try:
        text, secs, usage = chat(messages, **opts)
        if v == "canonical":
            passed, log = check_family(family, text)
        else:
            passed, log = check_variant(family, v, text)
    except sandbox.SandboxTimeout as e:
        error_kind, err_msg = "timeout", str(e)[:300]
        log = f"TIMEOUT: {err_msg}"
    except _MissingTool as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = f"infra: {err_msg}"
    except Exception as e:
        error_kind, err_msg = "missing-tool", str(e)[:300]
        log = f"executor-error: {err_msg}"
    status = _status_for(passed, error_kind)
    attempt = {
        "run_id": run_id,
        "model_id": model_id,
        "task_family_id": family,
        "instance_id": instance["instance_id"],
        "variant_class": v,
        "trial_id": trial_id,
        "primary_status": status,
        "score": 1.0 if status == "PASS" else 0.0,
        "eligible_for_task_score": status in ("PASS", "PARTIAL", "FAIL", "TIMEOUT", "INVALID"),
        "eligible_for_pass_rate": status in ("PASS", "PARTIAL", "FAIL", "TIMEOUT", "INVALID"),
        "eligible_for_efficiency": status in ("PASS", "PARTIAL", "FAIL"),
        "eligible_for_calibration": False,
        "primary_failure": None
        if status == "PASS"
        else (
            "TIMEOUT"
            if status == "TIMEOUT"
            else ("HARNESS_ERROR" if status == "ERROR" else "WRONG_RESULT")
        ),
        "secondary_failure_tags": [],
        "seed": seed,
        "reasoning_mode": reasoning_mode_for(opts.get("think"), opts.get("num_predict")),
        "secs": round(secs, 1) if isinstance(secs, (int, float)) else secs,
        "log": str(log)[-500:],
        "sample": (text or "")[:600],
        "prompt_sha256": instance["prompt_sha256"],
        "manifest_sha256": instance["manifest_sha256"],
    }
    if err_msg:
        attempt["error"] = err_msg
    response = {
        "instance_id": instance["instance_id"],
        "trial_id": trial_id,
        "messages": messages,
        "options": opts,
        "reply": text,
        "usage": usage if isinstance(usage, dict) else {},
    }
    return validate_attempt(attempt), response


def prompt_pack_sha256():
    """SHA256 over all canonical prompts (for run manifest prompt_sha256)."""
    blob = "".join(cases.prompt_text(f) for f in cases.FAMILY_IDS)
    return sha256_bytes(blob.encode("utf-8"))


def harness_sha256():
    """SHA256 of this executor file's bytes (for run manifest)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())


def _validate_run_id(run_id):
    """Confine run_id to a single path segment (audit H2).

    The runner generates run_ids via urandom, but write_raw_run is
    directly callable — a manifest with run_id '../../tmp/evil' must
    never escape out_root. Raises ValueError on refusal.
    """
    rid = run_id or ""
    if not rid or ".." in rid or "/" in rid or "\\" in rid or rid.startswith(".") or len(rid) > 128:
        raise ValueError(f"run_id refused: {rid[:60]!r}")


def write_raw_run(out_root, run_manifest, attempts, responses, environment=None):
    """Write results/raw/RUN-ID/ layout (SPEC 33). Returns run dir path.

    Atomic publish (audit H2): files are staged in a sibling temp dir
    and published with a single os.replace, so a crash never leaves a
    half-written bundle behind.
    """
    import tempfile

    manifest = validate_run_manifest(run_manifest)
    run_id = manifest.get("run_id", run_manifest.get("run_id", "RUN"))
    _validate_run_id(run_id)
    out_real = os.path.realpath(out_root)
    rundir = os.path.join(out_root, run_id)
    if os.path.commonpath([os.path.realpath(rundir), out_real]) != out_real:
        raise ValueError(f"run_id escapes out_root: {run_id[:60]!r}")
    staging = tempfile.mkdtemp(prefix=".stage-", dir=out_root)
    try:
        with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        with open(os.path.join(staging, "events.jsonl"), "w", encoding="utf-8") as f:
            for a in attempts:
                f.write(json.dumps(validate_attempt(a), ensure_ascii=False) + "\n")
        with open(os.path.join(staging, "responses.jsonl"), "w", encoding="utf-8") as f:
            for r in responses:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        env = dict(environment or {})
        env.setdefault("written_utc", datetime.datetime.now(datetime.timezone.utc).isoformat())
        with open(os.path.join(staging, "environment.json"), "w", encoding="utf-8") as f:
            json.dump(env, f, ensure_ascii=False, indent=1)
        if os.path.exists(rundir):
            raise FileExistsError(f"refusing to overwrite: {rundir!r}")
        os.replace(staging, rundir)
    except BaseException:
        import shutil as _shutil

        _shutil.rmtree(staging, ignore_errors=True)
        raise
    return rundir
