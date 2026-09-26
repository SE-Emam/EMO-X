"""EMO-X issues suite: GitHub-issue-style repair tasks (stdlib only).

SWE-bench measures real GitHub issues (% Resolved); EMO measures agent
capabilities (profile, trajectory, recovery). This suite bridges the
two: each family is a real-world-style issue report (title + repro +
expected behavior) over a fixture repo carrying a genuine bug, with a
SWE-bench-shaped oracle: visible FAIL_TO_PASS tests in the repo plus
HELD-OUT hidden tests executed post-episode. PASS requires fixture
tests green AND hidden tests green AND a FINAL stop — fixing only the
visible tests while breaking hidden behavior fails.

Families (bug class -> hidden generalization):
  IS1 csv-quoted-commas   naive split(',') breaks quoted fields;
                          hidden: embedded quotes/commas/empty fields.
  IS2 config-deep-merge   nested dicts overwritten instead of merged;
                          hidden: 3-level nesting, list-replace semantics.
  IS3 backoff-cap         exponential backoff ignores max_delay cap;
                          hidden: longer horizons, cap binding at all steps.

Deterministic, stdlib-only, pytest-verified. Raw records only;
no scoring here (X-3 owns it).
"""

import json
import os

SUITE = "issues"
FAMILY_IDS = ("IS1", "IS2", "IS3", "IS4", "IS5", "IS6", "IS7", "IS8",
              "IS9", "IS10", "IS11", "IS12", "IS13", "IS14", "IS15")
VARIANTS = ("canonical",)

ISSUES = {
    "IS1": {
        "title": "CSV parser breaks on quoted fields containing commas",
        "body": (
            "The lightweight `csvmini.parse_line` helper splits rows on "
            "every comma, so quoted fields like `\"Doe, Jane\"` come back "
            "as two columns. Repro: "
            "parse_line('a,\"b,c\",d') returns 4 fields instead of 3. "
            "Expected: RFC-4180 style double-quote handling — commas "
            "inside double quotes do not split, and `\"\"` inside a "
            "quoted field means one literal quote. "
            "Fix `csvmini/parser.py`; keep the `parse_line` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS2": {
        "title": "config_merge overwrites nested dicts instead of merging",
        "body": (
            "The `cfgtools.merge(base, override)` helper replaces nested "
            "dicts wholesale: "
            "merge({'db': {'host': 'h', 'port': 1}}, {'db': {'port': 2}}) "
            "loses `host`. Repro above returns "
            "`{'db': {'port': 2}}` instead of "
            "`{'db': {'host': 'h', 'port': 2}}`. "
            "Expected: recursive merge for dict-vs-dict; every other type "
            "(including lists) is replaced by the override. "
            "Fix `cfgtools/merge.py`; keep the `merge` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS3": {
        "title": "backoff delays ignore the max_delay cap",
        "body": (
            "The `retry.delays(attempts, base, max_delay)` helper grows "
            "past the cap: delays(5, 1.0, 10.0) returns "
            "`[1.0, 2.0, 4.0, 8.0, 16.0]` instead of capping at 10.0. "
            "Expected: exponential growth base*2**i capped at max_delay "
            "for EVERY step (delays never exceed the cap). "
            "Fix `retry/backoff.py`; keep the `delays` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS4": {
        "title": "urljoin produces double slashes or drops the separator",
        "body": (
            "The `urlx.join_url(base, path)` helper concatenates blindly: "
            "join_url('http://h/api/', '/users') returns "
            "'http://h/api//users' (double slash) and "
            "join_url('http://h/api', 'users') returns "
            "'http://h/apiusers' (missing slash). "
            "Expected: exactly one '/' between base and path in all four "
            "slash combinations. "
            "Fix `urlx/join.py`; keep the `join_url` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS5": {
        "title": "budget check passes when only one delay fits",
        "body": (
            "The `retrybudget.fits_in_budget` helper is wrong: "
            "fits_in_budget([4.0, 4.0], 5.0) returns True because it "
            "checks whether ANY single delay fits instead of the SUM. "
            "Repro above returns True instead of False. "
            "Expected: True iff sum(delays) <= budget (empty list fits). "
            "Fix `retrybudget/budget.py`; keep the `fits_in_budget` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS6": {
        "title": "validator ignores required keys, including nested ones",
        "body": (
            "The `jschem.is_valid(obj, schema)` helper never enforces "
            "`required`: is_valid({}, {'required': ['name']}) returns "
            "True, and nested {'properties': {'db': {'required': "
            "['host']}}} is never descended into. "
            "Expected: every key in `required` must exist in the object, "
            "recursively for dict-valued `properties`. "
            "Fix `jschem/validate.py`; keep the `is_valid` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS7": {
        "title": "dedup loses original order",
        "body": (
            "The `seqtools.dedup(items)` helper returns "
            "list(set(items)): dedup([3, 1, 3, 2, 1]) returns "
            "[1, 2, 3] instead of [3, 1, 2]. "
            "Expected: first-occurrence order preserved. "
            "Fix `seqtools/dedup.py`; keep the `dedup` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS8": {
        "title": "to_utc adds the offset instead of subtracting it",
        "body": (
            "The `tzconv.to_utc(hh_mm, offset_h)` helper converts a wall "
            "time with UTC offset to UTC, but adds: "
            "to_utc('10:00', +2) returns '12:00' instead of '08:00'. "
            "Repro above returns '12:00' instead of '08:00'. "
            "Expected: UTC = wall time MINUS offset, formatted 'HH:MM' "
            "zero-padded mod 24h. "
            "Fix `tzconv/convert.py`; keep the `to_utc` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS9": {
        "title": "TTL cache entries never expire",
        "body": (
            "The `ttlcache.Cache(ttl, now_fn)` helper stores values "
            "without timestamps: after c.set('k', 'v'), advancing the "
            "injected clock past ttl still returns 'v' from c.get('k'). "
            "Expected: get returns None once now_fn() - set_time >= ttl; "
            "overwriting a key refreshes its timestamp. "
            "Fix `ttlcache/cache.py`; keep the constructor and "
            "get/set signatures (clock stays injectable). "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS10": {
        "title": "to_bytes confuses decimal KB with binary KiB",
        "body": (
            "The `units.to_bytes(n, unit)` helper uses 1000 for every "
            "unit: to_bytes(1, 'KiB') returns 1000 instead of 1024. "
            "Repro above returns 1000 instead of 1024. "
            "Expected: KB/MB/GB use powers of 1000, KiB/MiB/GiB powers "
            "of 1024, B is identity; unknown units raise ValueError. "
            "Fix `units/convert.py`; keep the `to_bytes` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS11": {
        "title": "slugify leaves edge cases unhandled",
        "body": (
            "The `text.slugify(s)` helper lowercases and swaps spaces "
            "for dashes but never strips or collapses: "
            "slugify('  Hello   World  ') returns '--hello---world--' "
            "instead of 'hello-world'. "
            "Expected: lowercase, non-alphanumeric runs become one dash, "
            "leading/trailing dashes stripped. "
            "Fix `text/slug.py`; keep the `slugify` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS12": {
        "title": "batcher drops the last partial chunk",
        "body": (
            "The `batch.chunks(items, size)` helper drops the remainder: "
            "chunks([1, 2, 3, 4, 5], 2) returns [[1, 2], [3, 4]], losing "
            "[5]. "
            "Expected: all items covered, last chunk possibly shorter. "
            "Fix `batch/chunks.py`; keep the `chunks` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS13": {
        "title": "flatten_once flattens to full depth",
        "body": (
            "The `nest.flatten_once(nested)` helper recurses fully: "
            "flatten_once([[1, [2]], 3]) returns [1, 2, 3] instead of "
            "[[1, [2]], 3] flattened one level to [1, [2], 3]. "
            "Expected: exactly one level unwrapped, deeper lists kept "
            "as-is, non-list items passed through. "
            "Fix `nest/flat.py`; keep the `flatten_once` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS14": {
        "title": "env int config returns raw strings",
        "body": (
            "The `envcfg.get_int(name, default)` helper returns the raw "
            "environment string: with TIMEOUT='30', get_int('TIMEOUT', "
            "5) returns '30' (a str) instead of 30. "
            "Expected: int conversion; missing keys and non-numeric "
            "values fall back to default. "
            "Fix `envcfg/get.py`; keep the `get_int` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
    "IS15": {
        "title": "is_newer compares versions as plain strings",
        "body": (
            "The `ver.is_newer(a, b)` helper compares lexicographically: "
            "is_newer('1.10.0', '1.9.0') returns False because '1' < '9' "
            "at the second component. "
            "Expected: numeric per-component comparison, missing trailing "
            "components treated as 0. "
            "Fix `ver/compare.py`; keep the `is_newer` signature. "
            "Run `python3 -m pytest tests/ -x -q` until green, then stop "
            "with FINAL."),
    },
}

# --- fixture repos (buggy) -------------------------------------------------

def _files_is1():
    return {
        "csvmini/__init__.py": "",
        "csvmini/parser.py": (
            "def parse_line(line):\n"
            "    \"\"\"Split one CSV line into fields (bug: quotes ignored).\"\"\"\n"
            "    return line.split(\",\")\n"),
        "tests/test_parser.py": (
            "from csvmini.parser import parse_line\n\n"
            "def test_plain():\n"
            "    assert parse_line(\"a,b,c\") == [\"a\", \"b\", \"c\"]\n\n"
            "def test_quoted_comma():\n"
            "    assert parse_line('a,\"b,c\",d') == [\"a\", \"b,c\", \"d\"]\n"),
    }


def _files_is2():
    return {
        "cfgtools/__init__.py": "",
        "cfgtools/merge.py": (
            "def merge(base, override):\n"
            "    \"\"\"Merge override into base (bug: nesting flattened).\"\"\"\n"
            "    out = dict(base)\n"
            "    out.update(override)\n"
            "    return out\n"),
        "tests/test_merge.py": (
            "from cfgtools.merge import merge\n\n"
            "def test_flat():\n"
            "    assert merge({\"a\": 1}, {\"b\": 2}) == "
            "{\"a\": 1, \"b\": 2}\n\n"
            "def test_nested():\n"
            "    assert merge({\"db\": {\"host\": \"h\", \"port\": 1}}, "
            "{\"db\": {\"port\": 2}}) == "
            "{\"db\": {\"host\": \"h\", \"port\": 2}}\n"),
    }


def _files_is3():
    return {
        "retry/__init__.py": "",
        "retry/backoff.py": (
            "def delays(attempts, base, max_delay):\n"
            "    \"\"\"Attempt delays (bug: cap never applied).\"\"\"\n"
            "    return [base * (2 ** i) for i in range(attempts)]\n"),
        "tests/test_backoff.py": (
            "from retry.backoff import delays\n\n"
            "def test_growth():\n"
            "    assert delays(3, 1.0, 100.0) == [1.0, 2.0, 4.0]\n\n"
            "def test_cap():\n"
            "    assert delays(5, 1.0, 10.0) == [1.0, 2.0, 4.0, 8.0, 10.0]\n"),
    }


def _files_is4():
    return {
        "urlx/__init__.py": "",
        "urlx/join.py": (
            "def join_url(base, path):\n"
            "    \"\"\"Join base and path (bug: separator mishandled).\"\"\"\n"
            "    return base + path\n"),
        "tests/test_join.py": (
            "from urlx.join import join_url\n\n"
            "def test_both_plain():\n"
            "    assert join_url('http://h/api', 'users') == "
            "'http://h/api/users'\n\n"
            "def test_double_slash():\n"
            "    assert join_url('http://h/api/', '/users') == "
            "'http://h/api/users'\n"),
    }


def _files_is5():
    return {
        "retrybudget/__init__.py": "",
        "retrybudget/budget.py": (
            "def fits_in_budget(delays, budget):\n"
            "    \"\"\"True iff the delays fit (bug: ANY instead of SUM).\"\"\"\n"
            "    return any(d <= budget for d in delays)\n"),
        "tests/test_budget.py": (
            "from retrybudget.budget import fits_in_budget\n\n"
            "def test_fits():\n"
            "    assert fits_in_budget([1.0, 2.0], 5.0) is True\n\n"
            "def test_over():\n"
            "    assert fits_in_budget([4.0, 4.0], 5.0) is False\n"),
    }


def _files_is6():
    return {
        "jschem/__init__.py": "",
        "jschem/validate.py": (
            "def is_valid(obj, schema):\n"
            "    \"\"\"Validate obj (bug: required never enforced).\"\"\"\n"
            "    if not isinstance(obj, dict):\n"
            "        return False\n"
            "    return True\n"),
        "tests/test_validate.py": (
            "from jschem.validate import is_valid\n\n"
            "def test_valid():\n"
            "    assert is_valid({'name': 'a'}, "
            "{'required': ['name']}) is True\n\n"
            "def test_missing():\n"
            "    assert is_valid({}, {'required': ['name']}) is False\n"),
    }


def _files_is7():
    return {
        "seqtools/__init__.py": "",
        "seqtools/dedup.py": (
            "def dedup(items):\n"
            "    \"\"\"Deduplicate (bug: order lost via set).\"\"\"\n"
            "    return list(set(items))\n"),
        "tests/test_dedup.py": (
            "from seqtools.dedup import dedup\n\n"
            "def test_order():\n"
            "    assert dedup([3, 1, 3, 2, 1]) == [3, 1, 2]\n\n"
            "def test_empty():\n"
            "    assert dedup([]) == []\n"),
    }


def _files_is8():
    return {
        "tzconv/__init__.py": "",
        "tzconv/convert.py": (
            "def to_utc(hh_mm, offset_h):\n"
            "    \"\"\"Wall time to UTC (bug: offset added, not subtracted).\"\"\"\n"
            "    h, m = (int(x) for x in hh_mm.split(':'))\n"
            "    total = (h * 60 + m + int(offset_h * 60)) % (24 * 60)\n"
            "    return '%02d:%02d' % (total // 60, total % 60)\n"),
        "tests/test_convert.py": (
            "from tzconv.convert import to_utc\n\n"
            "def test_positive():\n"
            "    assert to_utc('10:00', 2) == '08:00'\n\n"
            "def test_zero():\n"
            "    assert to_utc('10:00', 0) == '10:00'\n"),
    }


def _files_is9():
    return {
        "ttlcache/__init__.py": "",
        "ttlcache/cache.py": (
            "class Cache:\n"
            "    \"\"\"TTL cache (bug: timestamps never stored).\"\"\"\n"
            "    def __init__(self, ttl, now_fn):\n"
            "        self.ttl = ttl\n"
            "        self.now_fn = now_fn\n"
            "        self.store = {}\n"
            "    def set(self, key, value):\n"
            "        self.store[key] = value\n"
            "    def get(self, key):\n"
            "        return self.store.get(key)\n"),
        "tests/test_cache.py": (
            "from ttlcache.cache import Cache\n\n"
            "def test_hit():\n"
            "    t = [0]\n"
            "    c = Cache(10, lambda: t[0])\n"
            "    c.set('k', 'v')\n"
            "    assert c.get('k') == 'v'\n\n"
            "def test_expiry():\n"
            "    t = [0]\n"
            "    c = Cache(10, lambda: t[0])\n"
            "    c.set('k', 'v')\n"
            "    t[0] = 11\n"
            "    assert c.get('k') is None\n"),
    }


def _files_is10():
    return {
        "units/__init__.py": "",
        "units/convert.py": (
            "def to_bytes(n, unit):\n"
            "    \"\"\"Convert to bytes (bug: all units decimal).\"\"\"\n"
            "    table = {'B': 1, 'KB': 1000, 'MB': 1000 ** 2,\n"
            "             'GB': 1000 ** 3, 'KiB': 1000, 'MiB': 1000 ** 2,\n"
            "             'GiB': 1000 ** 3}\n"
            "    return n * table[unit]\n"),
        "tests/test_convert.py": (
            "from units.convert import to_bytes\n\n"
            "def test_kb():\n"
            "    assert to_bytes(1, 'KB') == 1000\n\n"
            "def test_kib():\n"
            "    assert to_bytes(1, 'KiB') == 1024\n"),
    }


def _files_is11():
    return {
        "text/__init__.py": "",
        "text/slug.py": (
            "def slugify(s):\n"
            "    \"\"\"Slugify (bug: edges never cleaned).\"\"\"\n"
            "    return s.lower().replace(' ', '-')\n"),
        "tests/test_slug.py": (
            "from text.slug import slugify\n\n"
            "def test_basic():\n"
            "    assert slugify('Hello World') == 'hello-world'\n\n"
            "def test_edges():\n"
            "    assert slugify('  Hello   World  ') == 'hello-world'\n"),
    }


def _files_is12():
    return {
        "batch/__init__.py": "",
        "batch/chunks.py": (
            "def chunks(items, size):\n"
            "    \"\"\"Chunk list (bug: remainder dropped).\"\"\"\n"
            "    return [items[i:i + size]\n"
            "            for i in range(0, len(items) - size + 1, size)]\n"),
        "tests/test_chunks.py": (
            "from batch.chunks import chunks\n\n"
            "def test_even():\n"
            "    assert chunks([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]\n\n"
            "def test_remainder():\n"
            "    assert chunks([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]\n"),
    }


def _files_is13():
    return {
        "nest/__init__.py": "",
        "nest/flat.py": (
            "def flatten_once(nested):\n"
            "    \"\"\"Unwrap one level (bug: recurses to full depth).\"\"\"\n"
            "    out = []\n"
            "    for x in nested:\n"
            "        if isinstance(x, list):\n"
            "            out.extend(flatten_once(x))\n"
            "        else:\n"
            "            out.append(x)\n"
            "    return out\n"),
        "tests/test_flat.py": (
            "from nest.flat import flatten_once\n\n"
            "def test_flat():\n"
            "    assert flatten_once([1, [2], 3]) == [1, 2, 3]\n\n"
            "def test_depth():\n"
            "    assert flatten_once([[1, [2]], 3]) == [1, [2], 3]\n"),
    }


def _files_is14():
    return {
        "envcfg/__init__.py": "",
        "envcfg/get.py": (
            "import os as _os\n\n"
            "def get_int(name, default):\n"
            "    \"\"\"Env int (bug: raw string returned).\"\"\"\n"
            "    return _os.environ.get(name, default)\n"),
        "tests/test_get.py": (
            "import os\n"
            "from envcfg.get import get_int\n\n"
            "def test_cast(monkeypatch):\n"
            "    monkeypatch.setenv('TIMEOUT', '30')\n"
            "    assert get_int('TIMEOUT', 5) == 30\n\n"
            "def test_missing(monkeypatch):\n"
            "    monkeypatch.delenv('TIMEOUT', raising=False)\n"
            "    assert get_int('TIMEOUT', 5) == 5\n"),
    }


def _files_is15():
    return {
        "ver/__init__.py": "",
        "ver/compare.py": (
            "def is_newer(a, b):\n"
            "    \"\"\"Newer check (bug: lexicographic compare).\"\"\"\n"
            "    return a > b\n"),
        "tests/test_compare.py": (
            "from ver.compare import is_newer\n\n"
            "def test_simple():\n"
            "    assert is_newer('2.0.0', '1.9.9') is True\n\n"
            "def test_numeric_parts():\n"
            "    assert is_newer('1.10.0', '1.9.0') is True\n"),
    }


FIXTURES = {"IS1": _files_is1, "IS2": _files_is2, "IS3": _files_is3,
            "IS4": _files_is4, "IS5": _files_is5, "IS6": _files_is6,
            "IS7": _files_is7, "IS8": _files_is8, "IS9": _files_is9,
            "IS10": _files_is10, "IS11": _files_is11,
            "IS12": _files_is12, "IS13": _files_is13,
            "IS14": _files_is14, "IS15": _files_is15}

# --- held-out hidden tests (run post-episode, never shown to the agent) ---

HIDDEN_TESTS = {
    "IS1": (
        "from csvmini.parser import parse_line\n\n"
        "def test_empty_fields():\n"
        "    assert parse_line('a,,c') == ['a', '', 'c']\n\n"
        "def test_escaped_quote():\n"
        "    assert parse_line('\"a\"\"b\",c') == ['a\"b', 'c']\n\n"
        "def test_quoted_edge():\n"
        "    assert parse_line('\"x\",,\"y,z\"') == ['x', '', 'y,z']\n"),
    "IS2": (
        "from cfgtools.merge import merge\n\n"
        "def test_three_levels():\n"
        "    assert merge({\"a\": {\"b\": {\"c\": 1, \"d\": 2}}}, "
        "{\"a\": {\"b\": {\"d\": 3}}}) == "
        "{\"a\": {\"b\": {\"c\": 1, \"d\": 3}}}\n\n"
        "def test_lists_replaced():\n"
        "    assert merge({\"k\": [1, 2]}, {\"k\": [3]}) == {\"k\": [3]}\n\n"
        "def test_base_untouched():\n"
        "    b = {\"db\": {\"host\": \"h\"}}\n"
        "    merge(b, {\"db\": {\"port\": 2}})\n"
        "    assert b == {\"db\": {\"host\": \"h\"}}\n"),
    "IS3": (
        "from retry.backoff import delays\n\n"
        "def test_long_horizon_capped():\n"
        "    ds = delays(10, 0.5, 5.0)\n"
        "    assert len(ds) == 10\n"
        "    assert all(d <= 5.0 for d in ds)\n"
        "    assert ds == [0.5, 1.0, 2.0, 4.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0]\n\n"
        "def test_zero_attempts():\n"
        "    assert delays(0, 1.0, 10.0) == []\n"),
    "IS4": (
        "from urlx.join import join_url\n\n"
        "def test_trailing_base():\n"
        "    assert join_url('http://h/api/', 'users') == "
        "'http://h/api/users'\n\n"
        "def test_leading_path():\n"
        "    assert join_url('http://h/api', '/users') == "
        "'http://h/api/users'\n\n"
        "def test_empty_path():\n"
        "    assert join_url('http://h/api', '') == 'http://h/api/'\n"),
    "IS5": (
        "from retrybudget.budget import fits_in_budget\n\n"
        "def test_exact_boundary():\n"
        "    assert fits_in_budget([2.5, 2.5], 5.0) is True\n\n"
        "def test_empty_fits():\n"
        "    assert fits_in_budget([], 5.0) is True\n\n"
        "def test_single_over():\n"
        "    assert fits_in_budget([6.0], 5.0) is False\n"),
    "IS6": (
        "from jschem.validate import is_valid\n\n"
        "def test_nested_required():\n"
        "    assert is_valid({'db': {}}, "
        "{'properties': {'db': {'required': ['host']}}}) is False\n\n"
        "def test_non_dict_rejected():\n"
        "    assert is_valid([1, 2], {'required': ['a']}) is False\n\n"
        "def test_no_schema_passes_dict():\n"
        "    assert is_valid({'a': 1}, {}) is True\n"),
    "IS7": (
        "from seqtools.dedup import dedup\n\n"
        "def test_all_dup():\n"
        "    assert dedup([5, 5, 5]) == [5]\n\n"
        "def test_unsorted_pair():\n"
        "    assert dedup([2, 1, 2]) == [2, 1]\n\n"
        "def test_single():\n"
        "    assert dedup([1]) == [1]\n"),
    "IS8": (
        "from tzconv.convert import to_utc\n\n"
        "def test_negative():\n"
        "    assert to_utc('10:00', -5) == '15:00'\n\n"
        "def test_midnight_wrap():\n"
        "    assert to_utc('01:30', 3) == '22:30'\n\n"
        "def test_half_hour():\n"
        "    assert to_utc('10:00', 5.5) == '04:30'\n"),
    "IS9": (
        "from ttlcache.cache import Cache\n\n"
        "def test_overwrite_refreshes():\n"
        "    t = [0]\n"
        "    c = Cache(10, lambda: t[0])\n"
        "    c.set('k', 'v1')\n"
        "    t[0] = 9\n"
        "    c.set('k', 'v2')\n"
        "    t[0] = 15\n"
        "    assert c.get('k') == 'v2'\n"
        "    t[0] = 20\n"
        "    assert c.get('k') is None\n\n"
        "def test_missing_key():\n"
        "    c = Cache(10, lambda: 0)\n"
        "    assert c.get('nope') is None\n"),
    "IS10": (
        "from units.convert import to_bytes\n\n"
        "def test_mib():\n"
        "    assert to_bytes(2, 'MiB') == 2 * 1024 * 1024\n\n"
        "def test_bytes_identity():\n"
        "    assert to_bytes(7, 'B') == 7\n\n"
        "def test_unknown_raises():\n"
        "    try:\n"
        "        to_bytes(1, 'XB')\n"
        "    except (KeyError, ValueError):\n"
        "        return\n"
        "    raise AssertionError('unknown unit accepted')\n"),
    "IS11": (
        "from text.slug import slugify\n\n"
        "def test_empty():\n"
        "    assert slugify('') == ''\n\n"
        "def test_punct_collapse():\n"
        "    assert slugify('a -- b!!c') == 'a-b-c'\n\n"
        "def test_underscores():\n"
        "    assert slugify('a_b c') == 'a-b-c'\n"),
    "IS12": (
        "from batch.chunks import chunks\n\n"
        "def test_oversize():\n"
        "    assert chunks([1, 2], 5) == [[1, 2]]\n\n"
        "def test_empty():\n"
        "    assert chunks([], 3) == []\n\n"
        "def test_exact():\n"
        "    assert chunks([1, 2, 3], 3) == [[1, 2, 3]]\n"),
    "IS13": (
        "from nest.flat import flatten_once\n\n"
        "def test_already_flat():\n"
        "    assert flatten_once([1, 2, 3]) == [1, 2, 3]\n\n"
        "def test_empty_inner():\n"
        "    assert flatten_once([[[1]]]) == [[1]]\n\n"
        "def test_mixed():\n"
        "    assert flatten_once(['a', ['b', ['c']]]) == ['a', 'b', ['c']]\n"),
    "IS14": (
        "from envcfg.get import get_int\n\n"
        "def test_invalid_falls_back(monkeypatch):\n"
        "    monkeypatch.setenv('TIMEOUT', 'fast')\n"
        "    assert get_int('TIMEOUT', 5) == 5\n\n"
        "def test_zero_valid(monkeypatch):\n"
        "    monkeypatch.setenv('TIMEOUT', '0')\n"
        "    assert get_int('TIMEOUT', 5) == 0\n"),
    "IS15": (
        "from ver.compare import is_newer\n\n"
        "def test_equal_not_newer():\n"
        "    assert is_newer('1.2.3', '1.2.3') is False\n\n"
        "def test_major_dominates():\n"
        "    assert is_newer('2.0', '1.99.99') is True\n\n"
        "def test_double_digit_minor():\n"
        "    assert is_newer('1.9.0', '1.10.0') is False\n\n"
        "def test_trailing_zeros_equal():\n"
        "    assert is_newer('1.2', '1.2.0') is False\n"),
}


def issue_text(family):
    """Render the GitHub-issue-style task prompt for a family."""
    issue = ISSUES[family]
    return ("GitHub issue — %s\n\n%s" % (issue["title"], issue["body"]))


def load_manifest(family):
    """Load suites/issues/manifests/<family>.json."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "manifests", "%s.json" % family)
    with open(path, encoding="utf-8") as f:
        return json.load(f)
