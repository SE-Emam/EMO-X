"""Tests for shared/selftest.py (Y-2). SPEC section 35.

Covers: all 14 check names present; missing optional binary => SKIP row
(not FAIL) with overall ok; tampered checksum copy => fail-closed FAIL.
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import selftest

EXPECTED_NAMES = (
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


class TestSelftest(unittest.TestCase):
    def test_all_14_names_present(self):
        ok, rows = selftest.run_all_checks()
        assert [n for n, _, _ in rows] == list(EXPECTED_NAMES)
        assert len(rows) == 14
        assert isinstance(ok, bool)

    def test_rows_shape(self):
        _, rows = selftest.run_all_checks()
        for row in rows:
            name, passed, detail = row
            assert isinstance(name, str)
            assert isinstance(passed, bool)
            assert isinstance(detail, str)
            if passed and detail.startswith("SKIP"):
                assert detail.startswith("SKIP: ")

    def test_ok_iff_zero_fails(self):
        ok, rows = selftest.run_all_checks()
        assert ok == all(p for _, p, _ in rows)

    def test_missing_host_node_does_not_affect_container(self):
        real_which = shutil.which

        def masked(binary, *args, **kwargs):
            if binary == "node":
                return None
            return real_which(binary, *args, **kwargs)

        shutil.which = masked
        try:
            ok, rows = selftest.run_all_checks()
        finally:
            shutil.which = real_which
        by_name = {n: (p, d) for n, p, d in rows}
        passed, detail = by_name["node-executor"]
        assert passed
        assert not detail.startswith("SKIP: ")
        assert ok == all(p for _, p, _ in rows)
        assert ok  # the pinned container toolchain is authoritative

    def test_tampered_checksum_copy_fails_closed(self):
        tmp = tempfile.mkdtemp(prefix="selftest_tamper_")
        try:
            evil = os.path.join(tmp, "evil.txt")
            with open(evil, "w", encoding="utf-8") as f:
                f.write("tampered content")
            sums = os.path.join(tmp, "SHA256SUMS")
            with open(sums, "w", encoding="utf-8") as f:
                f.write("0" * 64 + "  evil.txt\n")
            old = selftest.SHA256SUMS_FILE
            selftest.SHA256SUMS_FILE = sums
            try:
                _, rows = selftest.run_all_checks()
            finally:
                selftest.SHA256SUMS_FILE = old
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        by_name = {n: (p, d) for n, p, d in rows}
        passed, _ = by_name["checksum-validation"]
        assert not passed


if __name__ == "__main__":
    unittest.main()
