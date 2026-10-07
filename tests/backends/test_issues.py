"""Tests for the issues suite (GitHub-issue-style repair tasks)."""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


CASES = _load("is_cases_tests", os.path.join(_ROOT, "suites", "issues", "cases.py"))
EXEC = _load("is_executor_tests", os.path.join(_ROOT, "suites", "issues", "executor.py"))

FIXES = {
    "IS1": (
        "csvmini/parser.py",
        "def parse_line(line):\n"
        "    import csv as _c, io as _io\n"
        "    return next(_c.reader(_io.StringIO(line)))\n",
    ),
    "IS2": (
        "cfgtools/merge.py",
        "def merge(base, override):\n"
        "    out = dict(base)\n"
        "    for k, v in override.items():\n"
        "        if k in out and isinstance(out[k], dict) "
        "and isinstance(v, dict):\n"
        "            out[k] = merge(out[k], v)\n"
        "        else:\n"
        "            out[k] = v\n"
        "    return out\n",
    ),
    "IS3": (
        "retry/backoff.py",
        "def delays(attempts, base, max_delay):\n"
        "    return [min(base * (2 ** i), max_delay) "
        "for i in range(attempts)]\n",
    ),
    "IS4": (
        "urlx/join.py",
        "def join_url(base, path):\n"
        "    if not path:\n"
        "        return base.rstrip('/') + '/'\n"
        "    return base.rstrip('/') + '/' + path.lstrip('/')\n",
    ),
    "IS5": (
        "retrybudget/budget.py",
        "def fits_in_budget(delays, budget):\n    return sum(delays) <= budget\n",
    ),
    "IS6": (
        "jschem/validate.py",
        "def is_valid(obj, schema):\n"
        "    if not isinstance(obj, dict):\n"
        "        return False\n"
        "    for key in schema.get('required', []):\n"
        "        if key not in obj:\n"
        "            return False\n"
        "    props = schema.get('properties', {})\n"
        "    for key, sub in props.items():\n"
        "        if key in obj and isinstance(sub, dict):\n"
        "            if not is_valid(obj[key], sub):\n"
        "                return False\n"
        "    return True\n",
    ),
    "IS7": (
        "seqtools/dedup.py",
        "def dedup(items):\n"
        "    seen, out = set(), []\n"
        "    for x in items:\n"
        "        if x not in seen:\n"
        "            seen.add(x)\n"
        "            out.append(x)\n"
        "    return out\n",
    ),
    "IS8": (
        "tzconv/convert.py",
        "def to_utc(hh_mm, offset_h):\n"
        "    h, m = (int(x) for x in hh_mm.split(':'))\n"
        "    total = (h * 60 + m - int(offset_h * 60)) % (24 * 60)\n"
        "    return '%02d:%02d' % (total // 60, total % 60)\n",
    ),
    "IS9": (
        "ttlcache/cache.py",
        "class Cache:\n"
        "    def __init__(self, ttl, now_fn):\n"
        "        self.ttl = ttl\n"
        "        self.now_fn = now_fn\n"
        "        self.store = {}\n"
        "    def set(self, key, value):\n"
        "        self.store[key] = (value, self.now_fn())\n"
        "    def get(self, key):\n"
        "        if key not in self.store:\n"
        "            return None\n"
        "        value, ts = self.store[key]\n"
        "        if self.now_fn() - ts >= self.ttl:\n"
        "            del self.store[key]\n"
        "            return None\n"
        "        return value\n",
    ),
    "IS10": (
        "units/convert.py",
        "def to_bytes(n, unit):\n"
        "    table = {'B': 1, 'KB': 1000, 'MB': 1000 ** 2,\n"
        "             'GB': 1000 ** 3, 'KiB': 1024,\n"
        "             'MiB': 1024 ** 2, 'GiB': 1024 ** 3}\n"
        "    if unit not in table:\n"
        "        raise ValueError(unit)\n"
        "    return n * table[unit]\n",
    ),
    "IS11": (
        "text/slug.py",
        "import re as _re\n"
        "def slugify(s):\n"
        "    s = _re.sub(r'[^a-z0-9]+', '-', s.lower())\n"
        "    return s.strip('-')\n",
    ),
    "IS12": (
        "batch/chunks.py",
        "def chunks(items, size):\n"
        "    return [items[i:i + size]\n"
        "            for i in range(0, len(items), size)]\n",
    ),
    "IS13": (
        "nest/flat.py",
        "def flatten_once(nested):\n"
        "    out = []\n"
        "    for x in nested:\n"
        "        if isinstance(x, list):\n"
        "            out.extend(x)\n"
        "        else:\n"
        "            out.append(x)\n"
        "    return out\n",
    ),
    "IS14": (
        "envcfg/get.py",
        "import os as _os\n\n"
        "def get_int(name, default):\n"
        "    raw = _os.environ.get(name)\n"
        "    if raw is None:\n"
        "        return default\n"
        "    try:\n"
        "        return int(raw)\n"
        "    except (TypeError, ValueError):\n"
        "        return default\n",
    ),
    "IS15": (
        "ver/compare.py",
        "def _parts(v):\n"
        "    return [int(x) for x in v.split('.')]\n\n"
        "def is_newer(a, b):\n"
        "    pa, pb = _parts(a), _parts(b)\n"
        "    n = max(len(pa), len(pb))\n"
        "    pa += [0] * (n - len(pa))\n"
        "    pb += [0] * (n - len(pb))\n"
        "    return pa > pb\n",
    ),
}


def _materialize(family, fix=False):
    root = tempfile.mkdtemp()
    files = dict(CASES.FIXTURES[family]())
    if fix:
        rel, content = FIXES[family]
        files[rel] = content
    for rel, content in files.items():
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
    return root


def _pytest(root, target):
    return subprocess.run(
        ["python3", "-m", "pytest", target, "-q"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )


class IssuesFixtureTests(unittest.TestCase):
    def test_all_fixtures_fail_before_fix(self):
        """Every family must fail visible pytest pre-fix (real bugs)."""
        for fam in (
            "IS1",
            "IS2",
            "IS3",
            "IS4",
            "IS5",
            "IS6",
            "IS7",
            "IS8",
            "IS9",
            "IS10",
            "IS11",
            "IS12",
            "IS13",
            "IS14",
            "IS15",
        ):
            root = _materialize(fam)
            try:
                p = _pytest(root, "tests/")
                self.assertNotEqual(p.returncode, 0, "%s passes pre-fix (not a real bug)" % fam)
            finally:
                shutil.rmtree(root, ignore_errors=True)

    def test_hidden_fails_before_fix(self):
        """Held-out tests must also fail pre-fix (no fixture-only bug)."""
        for fam in (
            "IS1",
            "IS2",
            "IS3",
            "IS4",
            "IS5",
            "IS6",
            "IS7",
            "IS8",
            "IS9",
            "IS10",
            "IS11",
            "IS12",
            "IS13",
            "IS14",
            "IS15",
        ):
            root = _materialize(fam)
            try:
                with open(os.path.join(root, "test_hidden_oracle_emo.py"), "w") as f:
                    f.write(CASES.HIDDEN_TESTS[fam])
                h = _pytest(root, "test_hidden_oracle_emo.py")
                self.assertNotEqual(h.returncode, 0, "%s hidden passes pre-fix" % fam)
            finally:
                shutil.rmtree(root, ignore_errors=True)

    def test_correct_fix_passes_both(self):
        """A genuine fix must satisfy visible AND hidden suites."""
        for fam in (
            "IS1",
            "IS2",
            "IS3",
            "IS4",
            "IS5",
            "IS6",
            "IS7",
            "IS8",
            "IS9",
            "IS10",
            "IS11",
            "IS12",
            "IS13",
            "IS14",
            "IS15",
        ):
            root = _materialize(fam, fix=True)
            try:
                p = _pytest(root, "tests/")
                with open(os.path.join(root, "test_hidden_oracle_emo.py"), "w") as f:
                    f.write(CASES.HIDDEN_TESTS[fam])
                h = _pytest(root, "test_hidden_oracle_emo.py")
                self.assertEqual(
                    p.returncode, 0, "%s fix fails visible: %s" % (fam, p.stdout[-400:])
                )
                self.assertEqual(
                    h.returncode, 0, "%s fix fails hidden: %s" % (fam, h.stdout[-400:])
                )
            finally:
                shutil.rmtree(root, ignore_errors=True)

    def test_manifests_validate(self):
        for fam in (
            "IS1",
            "IS2",
            "IS3",
            "IS4",
            "IS5",
            "IS6",
            "IS7",
            "IS8",
            "IS9",
            "IS10",
            "IS11",
            "IS12",
            "IS13",
            "IS14",
            "IS15",
        ):
            m = CASES.load_manifest(fam)
            self.assertEqual(m["id"], fam)
            self.assertGreater(m["estimated_human_minutes"], 0)
            self.assertEqual(m["oracle"]["type"], "pytest-suite+held-out")

    def test_issue_text_renders(self):
        for fam in (
            "IS1",
            "IS2",
            "IS3",
            "IS4",
            "IS5",
            "IS6",
            "IS7",
            "IS8",
            "IS9",
            "IS10",
            "IS11",
            "IS12",
            "IS13",
            "IS14",
            "IS15",
        ):
            text = CASES.issue_text(fam)
            self.assertTrue(text.startswith("GitHub issue — "))
            self.assertIn(CASES.ISSUES[fam]["title"], text)
            self.assertIn("FINAL", text)

    def test_bad_variant_raises(self):
        with self.assertRaises(TypeError):
            EXEC.run_family("IS1", None, run_id="R", model_id="m", trial_id=1, variant="novel")

    def test_unknown_family_raises(self):
        with self.assertRaises(KeyError):
            EXEC.run_family("IS99", None, run_id="R", model_id="m", trial_id=1)

    def test_hashes_stable(self):
        self.assertEqual(EXEC.prompt_pack_sha256(), EXEC.prompt_pack_sha256())
        self.assertEqual(len(EXEC.harness_sha256()), 64)


if __name__ == "__main__":
    unittest.main()
