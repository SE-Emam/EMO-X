"""Golden pass/fail fixtures for code25 families and expanded variants.

The all-family inventory test uses deterministic backend fixtures. Focused
tests run the new execution oracles through the real fail-closed sandbox.
"""

import importlib.util
import json
import os
import unittest
from unittest import mock

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SUITE = os.path.join(ROOT, "suites", "code-bench-25")


def _load_executor():
    path = os.path.join(SUITE, "executor.py")
    spec = importlib.util.spec_from_file_location("code25_all_families_executor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load code25 executor from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PYTHON_GOLDENS = {
    "T2": (
        "def fib(n):\n"
        "    a, b = 0, 1\n"
        "    for _ in range(n):\n"
        "        a, b = b, a + b\n"
        "    return a"
    ),
    "T3": "def is_even(n):\n    return n % 2 == 0",
    "T6": "def اجمع(a, b):\n    return a + b",
    "H4": (
        "def longest_pal(s):\n"
        "    best = ''\n"
        "    for center in range(len(s)):\n"
        "        for left, right in ((center, center), (center, center + 1)):\n"
        "            while left >= 0 and right < len(s) and s[left] == s[right]:\n"
        "                if right - left + 1 > len(best):\n"
        "                    best = s[left : right + 1]\n"
        "                left -= 1\n"
        "                right += 1\n"
        "    return best"
    ),
    "H5": (
        "import time\n"
        "class TokenBucket:\n"
        "    def __init__(self, rate, capacity):\n"
        "        self.rate, self.capacity = rate, capacity\n"
        "        self.tokens, self.updated = capacity, time.monotonic()\n"
        "    def _refill(self):\n"
        "        now = time.monotonic()\n"
        "        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)\n"
        "        self.updated = now\n"
        "    def allow(self):\n"
        "        self._refill()\n"
        "        if self.tokens < 1:\n"
        "            return False\n"
        "        self.tokens -= 1\n"
        "        return True\n"
        "    def wait_time(self):\n"
        "        self._refill()\n"
        "        return max(0.0, (1 - self.tokens) / self.rate)"
    ),
    "H6": (
        "def first_occurrence(a, x):\n"
        "    lo, hi, result = 0, len(a) - 1, -1\n"
        "    while lo <= hi:\n"
        "        mid = (lo + hi) // 2\n"
        "        if a[mid] >= x:\n"
        "            if a[mid] == x:\n"
        "                result = mid\n"
        "            hi = mid - 1\n"
        "        else:\n"
        "            lo = mid + 1\n"
        "    return result"
    ),
    "A16": (
        "import asyncio\n"
        "async def fetch(x):\n"
        "    return x * 2\n"
        "async def fetch_all():\n"
        "    return await asyncio.gather(fetch(1), fetch(2))"
    ),
    "T30": (
        "def get_user(username):\n"
        "    return db.execute(\n"
        "        'SELECT * FROM users WHERE username = ?', (username,)\n"
        "    ).fetchall()"
    ),
    "T33": (
        "def fetch_json(url, transport, sleep_fn):\n"
        "    for attempt in range(1, 4):\n"
        "        response = transport.get(url)\n"
        "        status = response.status_code\n"
        "        if 200 <= status < 300:\n"
        "            return {'ok': True, 'data': response.json(), "
        "'attempt_count': attempt, 'last_error': None}\n"
        "        error = f'HTTP {status}'\n"
        "        if 400 <= status < 500:\n"
        "            return {'ok': False, 'data': None, "
        "'attempt_count': attempt, 'last_error': error}\n"
        "        if not 500 <= status < 600 or attempt == 3:\n"
        "            return {'ok': False, 'data': None, "
        "'attempt_count': attempt, 'last_error': error}\n"
        "        sleep_fn(0.1 * (2 ** (attempt - 1)))"
    ),
    "T36": (
        "def migrate_and_query(connection):\n"
        "    connection.execute(\n"
        "        \"ALTER TABLE accounts ADD COLUMN status TEXT NOT NULL DEFAULT 'active'\"\n"
        "    )\n"
        "    return connection.execute(\n"
        "        'SELECT id, name FROM accounts WHERE status = ? ORDER BY id', "
        "('active',)\n"
        "    ).fetchall()"
    ),
}

JS_GOLDEN = "function sumArr(arr) { return arr.reduce((a, b) => a + b, 0); }"
T8_GOLDEN = "def add(a, b):\n    return a + b\nif __name__ == '__main__':\n    print(add(2, 3))"
RUST_GOLDEN = (
    "fn is_prime(n: u64) -> bool {\n"
    "    if n < 2 { return false; }\n"
    "    for d in 2..=((n as f64).sqrt() as u64) {\n"
    "        if n % d == 0 { return false; }\n"
    "    }\n"
    "    true\n"
    "}\n"
    "fn main() {\n"
    "    assert!(is_prime(7) && !is_prime(8));\n"
    '    println!("PRIME_OK");\n'
    "}"
)
PATCH_GOLDEN = (
    "--- calc.py\n"
    "+++ calc.py\n"
    "@@ -1,5 +1,5 @@\n"
    "-def total(items):\n"
    "+def sum_all(items):\n"
    "     s = 0\n"
    "     for i in items:\n"
    "         s += i\n"
    "     return s\n"
)
TS_GOLDEN = (
    "interface User { name: string; age: number }\n"
    'function greet(u: User): string { return "Hello, " + u.name; }'
)
POSTGRES_GOLDEN = "SELECT name FROM products WHERE price < 100 ORDER BY price DESC"

CALIBRATION_PATH = os.path.join(SUITE, "t9_calibration.json")
with open(CALIBRATION_PATH, encoding="utf-8") as _calibration_file:
    _T9_POSITIVE = next(
        item["reply"] for item in json.load(_calibration_file)["items"] if item["expected"] is True
    )
with open(CALIBRATION_PATH, encoding="utf-8") as _calibration_file:
    _T9_NEGATIVE = next(
        item["reply"] for item in json.load(_calibration_file)["items"] if item["expected"] is False
    )

GOLDEN_REPLIES = {
    "T2": (
        PYTHON_GOLDENS["T2"],
        "def fib(n):\n    return 0",
    ),
    "T3": (
        PYTHON_GOLDENS["T3"],
        "def is_even(n):\n    return True",
    ),
    "T4": (JS_GOLDEN, "function sumArr(arr) { return 0; }"),
    "T5": (
        "الإغلاق في جافاسكريبت مفهوم يربط دالة داخلية بنطاقها المعجمي الخارجي. "
        "تحتفظ الدالة بالوصول إلى متغيرات النطاق بعد انتهاء الدالة الخارجية. "
        "مثال: closure function scope.",
        "A closure is a function that remembers its lexical scope.",
    ),
    "T6": (
        "```python\n"
        + PYTHON_GOLDENS["T6"]
        + "\n```\nالدالة اجمع تجمع الرقمين، وهذا مثال على طريقة عملها.",
        "def اجمع(a, b):\n    return 0\n# لا شرح هنا",
    ),
    "T7": (
        '{"name":"Ada","languages":["Python","Rust","Go"],"years":10}',
        '{"name":"Ada","languages":["Python","Rust"],"years":"10"}',
    ),
    "T8": (T8_GOLDEN, "print(4)"),
    "T9": (_T9_POSITIVE, _T9_NEGATIVE),
    "T10": (
        "Uma função interna em JavaScript lembra o escopo léxico onde foi criada. "
        "Ela mantém o acesso às variáveis externas depois que a função externa "
        "termina. Exemplo: uma função retorna outra função.",
        "A closure remembers its lexical scope after the outer function ends.",
    ),
    "R1": (
        RUST_GOLDEN,
        'fn main() { println!("not prime"); }',
    ),
    "R2": (
        "SELECT name FROM users WHERE age > 30 ORDER BY age ASC;",
        "SELECT name FROM users WHERE age < 30;",
    ),
    "R3": (
        "git clone https://github.com/x/y.git\n"
        "git checkout -b feat-z\n"
        "git add -A\n"
        "git commit -m 'feat: z'\n"
        "git push origin feat-z",
        "git clone https://github.com/x/y.git\ngit checkout -b feat-z\ngit push origin feat-z",
    ),
    "R4": (
        '{"rewrites":[{"source":"/(.*)","destination":"/index.html"}]}',
        '{"rewrites":[]}',
    ),
    "R5": (
        "async function getActiveUsers() { const { data, error } = await "
        "supabase.from('users').select('id,name').eq('active', true); "
        "if (error) throw error; return data; }",
        "function getActiveUsers() { return fetch('/users'); }",
    ),
    "R6": (PATCH_GOLDEN, "not a unified diff"),
    "R7": (
        "<tool_call>\n<function=calculator.add>\n<parameter=a>\n17\n</parameter>\n"
        "<parameter=b>\n25\n</parameter>\n</function>\n</tool_call>",
        "<tool_call><function=calculator.add><parameter=a>18</parameter>"
        "<parameter=b>25</parameter></function></tool_call>",
    ),
    "R8": (
        "feat(auth): add login rate limiting",
        "update login handler",
    ),
    "R9": (
        "<html><style>body{display:flex;justify-content:center;align-items:center}"
        "button{background:blue}</style><button>Click me</button></html>",
        "<html><button>Click me</button></html>",
    ),
    "R10": (
        "import { useState } from 'react'; export default function Counter() { "
        "const [count, setCount] = useState(0); return <button "
        "onClick={() => setCount(count + 1)}>{count}</button>; }",
        "export default function Counter() { return <button>0</button>; }",
    ),
    "R11": (TS_GOLDEN, "interface User { name: string; age: string }"),
    "R12": (
        POSTGRES_GOLDEN + ";",
        "SELECT name FROM products WHERE price > 100;",
    ),
    "R13": (
        "FROM python:3.12-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt /app/requirements.txt\n"
        "RUN pip install -r requirements.txt\n"
        'CMD ["python", "app.py"]',
        "FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install .",
    ),
    "H1": ("The answer is 126.", "The answer is 127."),
    "H2": ("Solutions: 27, 36, 45, and 0.", "Solutions: 27, 36, and 45."),
    "H3": ("The remainder is 4.", "The remainder is 5."),
    "H4": (
        PYTHON_GOLDENS["H4"],
        "def longest_pal(s):\n    return s",
    ),
    "H5": (
        PYTHON_GOLDENS["H5"],
        "class TokenBucket:\n    def allow(self): return True\n    def wait_time(self): return 0",
    ),
    "H6": (
        PYTHON_GOLDENS["H6"],
        "def first_occurrence(a, x):\n    return -1",
    ),
    "A16": (
        PYTHON_GOLDENS["A16"],
        "import asyncio\nasync def fetch(x): return x\nasync def fetch_all(): return []",
    ),
    "T30": (
        PYTHON_GOLDENS["T30"],
        "def get_user(username):\n"
        "    return db.execute(f\"SELECT * FROM users WHERE username = '{username}'\").fetchall()",
    ),
    "T33": (
        PYTHON_GOLDENS["T33"],
        "def fetch_json(url, transport, sleep_fn):\n"
        "    response=transport.get(url)\n"
        "    return {'ok': response.status_code == 200, 'data': response.json(), "
        "'attempt_count': 1, 'last_error': None}",
    ),
    "T36": (
        PYTHON_GOLDENS["T36"],
        "def migrate_and_query(connection):\n"
        "    connection.execute('DROP TABLE accounts')\n"
        "    connection.execute('CREATE TABLE accounts(id INTEGER PRIMARY KEY, "
        'name TEXT, status TEXT NOT NULL DEFAULT "active")\')\n'
        "    return connection.execute('SELECT id,name FROM accounts').fetchall()",
    ),
}

T2_VARIANT_GOLDEN = (
    "def fib(n):\n"
    "    if not isinstance(n, int):\n"
    "        raise TypeError('n must be an integer')\n"
    "    if n < 0:\n"
    "        raise ValueError('n must be non-negative')\n"
    "    a, b = 0, 1\n"
    "    for _ in range(n):\n"
    "        a, b = b, a + b\n"
    "    return a"
)
T3_VARIANT_GOLDEN = (
    "def safe_average(values):\n"
    "    if not values:\n"
    "        return 0\n"
    "    return sum(values) / len(values)"
)
R2_VARIANT_GOLDEN = (
    "SELECT users.name, orders.amount FROM users "
    "JOIN orders ON users.id = orders.user_id "
    "WHERE orders.amount IS NOT NULL AND orders.amount > 100 "
    "ORDER BY users.id, orders.id;"
)
R5_VARIANT_GOLDEN = (
    "async function getActiveUsers(client, page, pageSize) {\n"
    "  const start = (page - 1) * pageSize;\n"
    "  const end = start + pageSize - 1;\n"
    "  const { data, error } = await client.from('users').select('id,name')\n"
    "    .eq('active', true).range(start, end);\n"
    "  if (error) throw error;\n"
    "  return data;\n"
    "}"
)


class GoldenBackend:
    """Deterministic stand-in for external execution services."""

    def __init__(self):
        self.compiled_rust_roots = set()

    def run_python_code(self, code, test, timeout=30):
        expected = {
            "FIB_OK": PYTHON_GOLDENS["T2"],
            "FIX_OK": PYTHON_GOLDENS["T3"],
            "ARCODE_OK": PYTHON_GOLDENS["T6"],
            "PAL_OK": PYTHON_GOLDENS["H4"],
            "TB_OK": PYTHON_GOLDENS["H5"],
            "BS_OK": PYTHON_GOLDENS["H6"],
            "ASYNC_OK": PYTHON_GOLDENS["A16"],
            "T30_OK": PYTHON_GOLDENS["T30"],
            "T33_OK": PYTHON_GOLDENS["T33"],
            "T36_OK": PYTHON_GOLDENS["T36"],
        }
        marker = next((name for name in expected if name in test), None)
        if marker is not None and code.strip() == expected[marker].strip():
            return True, marker
        return False, "golden fixture rejected"

    def run_in_sandbox(self, argv, sandbox_dir=None, timeout=30, input_text=None):
        if argv[0] == "node":
            source = argv[2].split("\nif (sumArr", 1)[0]
            return (0, "JS_OK") if source == JS_GOLDEN else (1, "golden fixture rejected")
        if argv[0] == "python3" and "-c" in argv:
            source = argv[argv.index("-c") + 1]
            return (0, "5") if source == T8_GOLDEN else (1, "golden fixture rejected")
        if argv[0] == "rustc":
            source_path = os.path.join(sandbox_dir, "t.rs")
            with open(source_path, encoding="utf-8") as source_file:
                source = source_file.read()
            if source == RUST_GOLDEN:
                self.compiled_rust_roots.add(sandbox_dir)
                return 0, ""
            return 1, "golden fixture rejected"
        if argv[0] == "./t":
            return (0, "PRIME_OK") if sandbox_dir in self.compiled_rust_roots else (1, "")
        if argv[0] == "patch":
            if input_text != PATCH_GOLDEN:
                return 1, "golden fixture rejected"
            if "--dry-run" in argv:
                return 0, "patch would apply"
            target = os.path.join(sandbox_dir, "calc.py")
            with open(target, "w", encoding="utf-8") as target_file:
                target_file.write(
                    "def sum_all(items):\n    s = 0\n    for i in items:\n        s += i\n    return s\n"
                )
            return 0, "patch applied"
        if argv[0] == "tsc":
            source_path = os.path.join(sandbox_dir, "t.ts")
            with open(source_path, encoding="utf-8") as source_file:
                source = source_file.read()
            expected = TS_GOLDEN + '\nconst _chk: string = greet({name: "Test", age: 1});\n'
            return (0, "") if source == expected else (1, "golden fixture rejected")
        if argv[0] == "psql":
            command = argv[argv.index("-c") + 1]
            return (
                (0, "Keyboard\nMouse\n")
                if command.rstrip().endswith(POSTGRES_GOLDEN)
                else (0, "Monitor\n")
            )
        raise AssertionError(f"unexpected sandbox command: {argv!r}")


class AllFamiliesGoldenTests(unittest.TestCase):
    def test_t30(self):
        executor = _load_executor()
        passed, log = executor.check_family("T30", PYTHON_GOLDENS["T30"])
        self.assertTrue(passed, log)
        passed, log = executor.check_family("T30", GOLDEN_REPLIES["T30"][1])
        self.assertFalse(passed, log)

    def test_t33(self):
        executor = _load_executor()
        passed, log = executor.check_family("T33", PYTHON_GOLDENS["T33"])
        self.assertTrue(passed, log)

        no_retry = (
            "def fetch_json(url, transport, sleep_fn):\n"
            "    response = transport.get(url)\n"
            "    return {'ok': response.status_code == 200, 'data': response.json(), "
            "'attempt_count': 1, 'last_error': None}"
        )
        retries_4xx = (
            "def fetch_json(url, transport, sleep_fn):\n"
            "    for attempt in range(1, 4):\n"
            "        response=transport.get(url)\n"
            "        if response.status_code == 200:\n"
            "            return {'ok':True,'data':response.json(),'attempt_count':attempt,"
            "'last_error':None}\n"
            "        if attempt < 3: sleep_fn(0.1 * 2 ** (attempt - 1))\n"
            "    return {'ok':False,'data':None,'attempt_count':3,'last_error':'HTTP 404'}"
        )
        for source in (no_retry, retries_4xx):
            with self.subTest(source=source):
                passed, log = executor.check_family("T33", source)
                self.assertFalse(passed, log)

    def test_t36(self):
        executor = _load_executor()
        passed, log = executor.check_family("T36", PYTHON_GOLDENS["T36"])
        self.assertTrue(passed, log)
        passed, log = executor.check_family("T36", GOLDEN_REPLIES["T36"][1])
        self.assertFalse(passed, log)

    def test_expanded_task_variants(self):
        executor = _load_executor()
        cases = (
            ("T2", T2_VARIANT_GOLDEN, "def fib(n):\n    return 0"),
            ("T3", T3_VARIANT_GOLDEN, "def safe_average(values): return sum(values)//len(values)"),
            ("R2", R2_VARIANT_GOLDEN, "SELECT name FROM users"),
        )
        for family, positive, negative in cases:
            with self.subTest(family=family, result="positive"):
                self.assertTrue(executor.check_variant(family, "perturbed", positive)[0])
            with self.subTest(family=family, result="negative"):
                self.assertFalse(executor.check_variant(family, "perturbed", negative)[0])
        self.assertTrue(executor.check_variant("R5", "perturbed", R5_VARIANT_GOLDEN)[0])

        manifest_path = os.path.join(SUITE, "manifests", "T2.json")
        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
        with mock.patch.object(
            executor.sandbox, "run_python_code", return_value=(True, "T2_VARIANT_OK")
        ):
            attempt, response = executor.run_family(
                "T2",
                lambda messages, **_options: (T2_VARIANT_GOLDEN, 0.01, {}),
                run_id="golden",
                model_id="fixture",
                manifest=manifest,
                variant="perturbed",
            )
        self.assertEqual(attempt["variant_class"], "perturbed")
        self.assertEqual(attempt["instance_id"], "T2-perturbed-00001")
        self.assertEqual(
            response["messages"][0]["content"], executor.cases.variant_prompt("T2", "perturbed")
        )

    def test_r10_oracle_is_case_insensitive_for_component_identifiers(self):
        executor = _load_executor()
        realistic = (
            "import { useState } from 'react'; "
            "export default function Counter() { "
            "const [count, setCount] = useState(0); "
            "return <button onClick={() => setCount(count + 1)}>{count}</button>; }"
        )
        lower_case_names = (
            "import { usestate } from 'react'; "
            "export default function counter() { "
            "const [count, setcount] = usestate(0); "
            "return <button onclick={() => setcount(count + 1)}>{count}</button>; }"
        )
        self.assertTrue(executor.check_family("R10", realistic)[0])
        self.assertTrue(executor.check_family("R10", lower_case_names)[0])

    def test_every_family_has_canonical_golden_pass_and_fail(self):
        executor = _load_executor()
        backend = GoldenBackend()
        self.assertEqual(set(GOLDEN_REPLIES), set(executor.cases.FAMILY_IDS))
        self.assertEqual(len(GOLDEN_REPLIES), 32)

        with (
            mock.patch.object(
                executor.sandbox, "run_python_code", side_effect=backend.run_python_code
            ),
            mock.patch.object(
                executor.sandbox, "run_in_sandbox", side_effect=backend.run_in_sandbox
            ),
        ):
            for family in executor.cases.FAMILY_IDS:
                positive, negative = GOLDEN_REPLIES[family]
                with self.subTest(family=family, result="positive"):
                    passed, log = executor.check_family(family, positive)
                    self.assertTrue(passed, log)
                with self.subTest(family=family, result="negative"):
                    passed, log = executor.check_family(family, negative)
                    self.assertFalse(passed, log)

    def test_r4_rejects_malformed_and_semantically_wrong_configurations(self):
        executor = _load_executor()
        invalid_replies = (
            '{"rewrites": [}',
            '{"rewrites": {"source": "/(.*)", "destination": "/index.html"}}',
            '{"rewrites":[{"source":"/specific","destination":"/index.html"}]}',
            '{"rewrites":[{"source":"/(.*)","destination":"/other/index.html"}]}',
            '{"rewrites":[{"source":"/index.html","destination":"/other"}]}',
        )
        for reply in invalid_replies:
            with self.subTest(reply=reply):
                passed, _ = executor.check_family("R4", reply)
                self.assertFalse(passed)

    def test_r13_rejects_invalid_or_semantically_wrong_dockerfiles(self):
        executor = _load_executor()
        invalid_dockerfiles = (
            "FROM alpine:latest\n"
            "WORKDIR /app\nCOPY requirements.txt .\n"
            "RUN pip install -r requirements.txt\nCMD python app.py",
            "FROM python:3.12-slim\n"
            "WORKDIR /app\nCOPY requirements.txt .\n"
            "RUN echo 'pip install'\nCMD python app.py",
            "FROM python:3.12-slim\n"
            "WORKDIR /app\nCOPY other.txt .\n"
            "RUN pip install -r requirements.txt\nCMD python app.py",
            "FROM python:3.12-slim\n"
            "WORKDIR /app\nCOPY requirements.txt .\n"
            'RUN pip install "unterminated\nCMD python app.py',
            "FROM python:3.12-slim\n"
            "WORKDIR /app\nCOPY requirements.txt .\n"
            'RUN ["pip", "install",]\nCMD ["python", "app.py"]',
            "CMD python app.py\n"
            "FROM python:3.12-slim\nWORKDIR /app\n"
            "COPY requirements.txt .\nRUN pip install -r requirements.txt",
        )
        for dockerfile in invalid_dockerfiles:
            with self.subTest(dockerfile=dockerfile):
                passed, _ = executor.check_family("R13", dockerfile)
                self.assertFalse(passed)

    def test_r13_accepts_valid_json_array_instructions(self):
        executor = _load_executor()
        dockerfile = (
            "FROM python:3.12-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt /app/requirements.txt\n"
            'RUN ["pip", "install", "-r", "requirements.txt"]\n'
            'CMD ["python", "app.py"]'
        )
        passed, log = executor.check_family("R13", dockerfile)
        self.assertTrue(passed, log)

    def test_family_manifests_declare_supported_variants(self):
        for filename in os.listdir(os.path.join(SUITE, "manifests")):
            if not filename.endswith(".json"):
                continue
            with open(os.path.join(SUITE, "manifests", filename), encoding="utf-8") as f:
                manifest = json.load(f)
            expected = (
                ["canonical", "perturbed", "novel"] if manifest["id"] == "H3" else ["canonical"]
            )
            if manifest["id"] in {"T2", "T3", "R2", "R5"}:
                expected = ["canonical", "perturbed"]
            self.assertEqual(manifest["variants"], expected, manifest["id"])


if __name__ == "__main__":
    unittest.main()
