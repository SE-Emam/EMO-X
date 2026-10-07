"""Extended harness self-test (Y-2). SPEC section 35.

Owns: the 14-check fail-closed harness verification behind
``run_all_checks()->(ok, rows)``, row-for-row compatible with
``runner.run_self_test`` so Y-INT can swap the call site without touching
``shared/runner.py``.

Row contract (binding, mirrors runner.run_self_test):
  rows are (name, bool, detail) tuples; detail is a short string.
  Missing optional binaries (node/rustc/tsc/psql/patch) produce
  (name, True, "SKIP: <reason>") -- SKIP is not FAIL.
  Overall ok is True iff zero FAILs.

Check-to-SPEC-35 mapping (14 checks):
  code-extraction      SPEC 35 executor chain (bench_lib.extract_code)
  python-executor      SPEC 35 "Python executor"
  node-executor        SPEC 35 "Node executor"
  rust-compiler        SPEC 35 "Rust compiler"
  typescript-compiler  SPEC 35 "TypeScript compiler"
  sqlite               SPEC 35 "SQLite"
  postgres-connection  SPEC 35 "PostgreSQL"
  patch-engine         SPEC 35 "Patch engine" (bench_lib.verify_patch)
  json-parser          SPEC 35 "JSON parser"
  timeout-enforcement  SPEC 35 "timeouts"
  forbidden-path-guard SPEC 35 "forbidden paths" (+ SPEC 24 sandbox_only)
  result-schema        SPEC 35 "result schema" (SPEC 32-34 validators)
  checksum-validation  SPEC 35 "hashing" (prompts/SHA256SUMS vs real files)
  golden-outputs       SPEC 35 "scoring" + "golden outputs" (hand-checked)

Reuses bench_lib/sandbox/scoring/manifests helpers; stdlib only.
English code.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import bench_lib
    import manifests
    import sandbox
    import schemas
    import scoring
except ImportError:  # `python shared/selftest.py` vs package import
    from shared import bench_lib, manifests, sandbox, schemas, scoring

#: Canonical check names in run order (binding for tests/Y-INT). SPEC 35.
CHECK_NAMES = (
    "code-extraction",
    "python-executor",
    "node-executor",
    "rust-compiler",
    "typescript-compiler",
    "sqlite",
    "postgres-connection",
    "patch-engine",
    "json-parser",
    "timeout-enforcement",
    "forbidden-path-guard",
    "result-schema",
    "checksum-validation",
    "golden-outputs",
)

#: Prompt-pack checksum file verified by checksum-validation. SPEC 35.
#: Module-level (read at call time) so tests can monkeypatch a tampered
#: copy in and expect a fail-closed FAIL row.
SHA256SUMS_FILE = os.path.join(ROOT, "prompts", "SHA256SUMS")


class _SkipCheck(Exception):
    """Raised when an optional binary is absent: SKIP, not FAIL. SPEC 35."""


# ---------------------------------------------------------------------------
# Individual checks (each returns a detail string; _SkipCheck => SKIP row;
# any other exception => FAIL row, fail-closed per SPEC 35).
# ---------------------------------------------------------------------------


def _check_code_extraction():
    """bench_lib.extract_code pulls the fenced block; no binary. SPEC 35."""
    sample = "prefix text\n```python\nprint(6 * 7)\n```\ntrailing\n"
    code = bench_lib.extract_code(sample, lang="python")
    if "print(6 * 7)" not in code:
        raise AssertionError(f"extract_code missed fenced block: {code!r}")
    other = bench_lib.extract_code(
        "```js\nx();\n```\n```python\ny();\n```", lang="python"
    )
    if "y();" not in other:
        raise AssertionError(f"extract_code lang filter broken: {other!r}")
    return "ok"


def _check_python_executor():
    """Sandboxed python executes model code. SPEC 35."""
    ok, log = sandbox.run_python_code(
        "x = 6 * 7", "assert x == 42\nprint('SELFTEST_PY')", timeout=30
    )
    if not ok or "SELFTEST_PY" not in log:
        raise AssertionError(f"python executor failed: {log[-200:]}")
    return "ok"


def _check_node_executor():
    """Node executes model JS in the isolation container. SPEC 35."""
    ok, log = bench_lib.run_js(
        "const x = 41;", "if (x + 1 !== 42) { throw new Error('bad'); }", timeout=30
    )
    if not ok:
        raise AssertionError(f"node executor failed: {log[-200:]}")
    return "ok"


def _check_rust_compiler():
    """rustc compiles+runs a hello program in the container. SPEC 35."""
    ok, log = bench_lib.run_rust('fn main() { println!("SELFTEST_RUST"); }')
    if not ok:
        raise AssertionError(f"rustc check failed: {log[-200:]}")
    return "ok"


def _check_typescript_compiler():
    """tsc --strict type-checks inside the isolation container. SPEC 35."""
    code = (
        "interface User { name: string; age: number }\n"
        "function greet(u: User): string { return u.name; }\n"
    )
    ok, log = bench_lib.verify_tsc(code)
    if not ok:
        raise AssertionError(f"tsc check failed: {log[-200:]}")
    return "ok"


def _check_sqlite():
    """In-memory sqlite round-trip via bench_lib helper. SPEC 35."""
    rows, err = bench_lib.sqlite_query(
        "SELECT SUM(a) FROM t;",
        "CREATE TABLE t(a INTEGER); INSERT INTO t VALUES (1);"
        " INSERT INTO t VALUES (2);",
        [],
    )
    if err is not None or rows != [(3,)]:
        raise AssertionError(f"sqlite check failed: {rows!r} {err!r}")
    return "ok"


def _check_postgres_connection():
    """psql scratch instance answers SELECT 1. SPEC 35.

    Missing binary => SKIP. Binary present but no reachable scratch
    instance => SKIP too: connectivity to the external scratch DB (see
    code-bench-25/SKILL.md) is environmental, not a harness defect, so it
    must not fail-close the whole self-test.
    """
    rows, rc, err = bench_lib.psql_query("SELECT 1;", "SELECT 1;", timeout=15)
    if rows is None or rc != 0:
        raise _SkipCheck(
            "postgres instance unavailable: %s" % (err or "connection failed")
        )
    return "ok"


def _check_patch_engine():
    """`patch` applies a unified diff inside the isolation container."""
    diff = "--- a.txt\n+++ a.txt\n@@ -1 +1 @@\n-hello\n+hello world\n"
    ok, log = bench_lib.verify_patch(
        "a.txt", "hello\n", diff, must_contain=("hello world",)
    )
    if not ok:
        raise AssertionError(f"patch check failed: {log[-200:]}")
    return "ok"


def _check_json_parser():
    """JSON round-trip. SPEC 35."""
    if json.loads('{"a": [1, 2]}') != {"a": [1, 2]}:
        raise AssertionError("json parser broken")
    return "ok"


def _check_timeout_enforcement():
    """Overrunning sandboxed command raises SandboxTimeout. SPEC 35."""
    try:
        sandbox.run_in_sandbox(
            ["python3", "-c", "import time; time.sleep(30)"], timeout=2
        )
    except sandbox.SandboxTimeout:
        return "ok"
    raise AssertionError("timeout did not fire")


def _check_forbidden_path_guard():
    """Escapes and forbidden prefixes are refused. SPEC 24 + SPEC 35."""
    root = sandbox.create_sandbox()
    try:
        for bad in ("../../etc/passwd", "/etc/passwd", "/var/run/secrets/tok"):
            try:
                sandbox.resolve_sandbox_path(root, bad)
            except sandbox.SandboxPathEscape:
                continue
            raise AssertionError(f"allowed forbidden path: {bad!r}")
    finally:
        sandbox.destroy_sandbox(root)
    return "ok"


def _check_result_schema():
    """validate_attempt accepts valid, rejects missing trial_id. SPEC 35."""
    schemas.validate_attempt(
        {
            "run_id": "R",
            "model_id": "M",
            "task_family_id": "T",
            "instance_id": "I",
            "variant_class": "canonical",
            "trial_id": 1,
            "primary_status": "PASS",
            "score": 1.0,
        }
    )
    try:
        schemas.validate_attempt(
            {
                "run_id": "R",
                "model_id": "M",
                "task_family_id": "T",
                "instance_id": "I",
                "variant_class": "canonical",
                "primary_status": "PASS",
                "score": 1.0,
            }
        )
    except Exception:
        return "ok"
    raise AssertionError("schema accepted a record without trial_id")


def _check_checksum_validation():
    """Every prompts/SHA256SUMS entry matches its real file. SPEC 35.

    Fail-closed: missing file, missing entry target, or hash mismatch
    FAILs (never SKIP): tampering must block benchmark execution.
    """
    sums_file = SHA256SUMS_FILE  # read global at call time (monkeypatchable)
    if not os.path.isfile(sums_file):
        raise AssertionError(f"SHA256SUMS not found: {sums_file}")
    base = os.path.dirname(sums_file)
    entries = []
    with open(sums_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                raise AssertionError(f"bad SHA256SUMS line: {line!r}")
            digest, name = parts[0], parts[-1].lstrip("*")
            entries.append((digest, name))
    if not entries:
        raise AssertionError("SHA256SUMS has no entries")
    for digest, name in entries:
        target = os.path.normpath(os.path.join(base, name))
        if not os.path.isfile(target):
            raise AssertionError(f"checksummed file missing: {name}")
        actual = manifests.sha256_file(target)
        if actual != digest:
            raise AssertionError(f"checksum mismatch (FAIL closed): {name}")
    return "ok (%d files)" % len(entries)


def _check_golden_outputs():
    """Hand-checked scoring values. SPEC 35 ('scoring', 'golden outputs').

    pass@k(5,3,2) = 1 - C(2,2)/C(5,2) = 1 - 1/10 = 0.9 (SPEC B10).
    brier([(0.8,1),(0.2,0)]) = ((0.04)+(0.04))/2 = 0.04 (SPEC B32).
    consistency@k(5,3,2) = C(3,2)/C(5,2) = 3/10 = 0.3 (SPEC B11).
    """
    if scoring.pass_at_k(5, 3, 2) != 0.9:
        raise AssertionError("pass_at_k golden mismatch")
    brier = scoring.brier_score(
        [{"confidence": 0.8, "outcome": 1}, {"confidence": 0.2, "outcome": 0}]
    )
    if brier is None or abs(brier - 0.04) > 1e-9:
        raise AssertionError(f"brier golden mismatch: {brier!r}")
    if scoring.consistency_at_k(5, 3, 2) != 0.3:
        raise AssertionError("consistency_at_k golden mismatch")
    return "ok"


_CHECKS = (
    ("code-extraction", _check_code_extraction),
    ("python-executor", _check_python_executor),
    ("node-executor", _check_node_executor),
    ("rust-compiler", _check_rust_compiler),
    ("typescript-compiler", _check_typescript_compiler),
    ("sqlite", _check_sqlite),
    ("postgres-connection", _check_postgres_connection),
    ("patch-engine", _check_patch_engine),
    ("json-parser", _check_json_parser),
    ("timeout-enforcement", _check_timeout_enforcement),
    ("forbidden-path-guard", _check_forbidden_path_guard),
    ("result-schema", _check_result_schema),
    ("checksum-validation", _check_checksum_validation),
    ("golden-outputs", _check_golden_outputs),
)

assert tuple(n for n, _ in _CHECKS) == CHECK_NAMES  # binding: names in order


def run_all_checks():
    """Fail-closed harness verification. SPEC 35.

    Returns (ok, rows) where rows are (name, bool, detail) tuples exactly
    like runner.run_self_test. Y-INT swaps the runner call to this function.
    ok is True iff zero checks FAIL (SKIP rows carry True + "SKIP: ...").
    Callers must refuse benchmark execution when ok is False (fail closed).
    """
    rows = []
    for name, func in _CHECKS:
        try:
            detail = func()
        except _SkipCheck as e:
            detail = " ".join(str(e).split())[:200]  # single-line detail
            rows.append((name, True, f"SKIP: {detail}"))
        except Exception as e:  # fail-closed: any error fails the check
            rows.append((name, False, str(e)[:200]))
        else:
            rows.append((name, True, detail))
    return all(ok for _, ok, _ in rows), rows


if __name__ == "__main__":
    ok, rows = run_all_checks()
    for name, passed, detail in rows:
        print("%-20s %s  %s" % (name, "PASS" if passed else "FAIL", detail))
    sys.exit(0 if ok else 1)
