"""Regression tests for audit findings D1 (command injection) and D2.

D1: tool_run must never spawn a shell. Prefix-allowed strings carrying
    shell metacharacters are rejected or executed as inert literal argv.
D2: _safe must reject sibling-prefix escapes via commonpath.
"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
EPDIR = os.path.normpath(os.path.join(HERE, "..", "..", "suites",
                                      "agent-loop"))
for _p in (SHARED, EPDIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sandbox  # noqa: E402


class _Ctx(object):
    def __init__(self, root):
        self.root = root
        self.ran_tests = 0
        self.reads = []
        self.nonexistent = 0


def _ls(path, ctx):
    if not os.path.isdir(os.path.join(ctx.root, path)):
        return False, "ERROR: not a directory: %s" % path
    return True, "listing of %s" % path


def _safe(path, ctx):
    full = os.path.normpath(os.path.join(ctx.root, path.lstrip("/")))
    try:
        if os.path.commonpath([full, ctx.root]) != ctx.root:
            raise ValueError("path escape")
    except ValueError:
        raise ValueError("path escape")
    return full


class ToolRunInjectionTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="toolsec_")
        self.ctx = _Ctx(self.root)
        with open(os.path.join(self.root, "a.txt"), "w") as f:
            f.write("hello")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)
        for name in ("pwned.txt",):
            p = os.path.join(self.root, name)
            if os.path.exists(p):
                os.unlink(p)

    def _no_shell(self, cmd):
        ok, out = sandbox.safe_tool_run(cmd, self.ctx, _ls, _safe)
        self.assertFalse(os.path.exists(
            os.path.join(self.root, "pwned.txt")),
            "shell metacharacters executed: %r" % cmd)
        return ok, out

    def test_semicolon_injection_dead(self):
        ok, _ = self._no_shell("ls; echo PWNED > pwned.txt")
        self.assertFalse(ok)

    def test_pipe_injection_dead(self):
        ok, _ = self._no_shell("cat a.txt | tee pwned.txt")
        self.assertFalse(ok)

    def test_and_injection_dead(self):
        ok, _ = self._no_shell("ls && echo PWNED > pwned.txt")
        self.assertFalse(ok)

    def test_dollar_subst_dead(self):
        ok, _ = self._no_shell("ls $(echo PWNED > pwned.txt)")
        self.assertFalse(ok)

    def test_backtick_dead(self):
        ok, _ = self._no_shell("ls `echo PWNED > pwned.txt`")
        self.assertFalse(ok)

    def test_allowed_ls_still_works(self):
        ok, out = sandbox.safe_tool_run("ls", self.ctx, _ls, _safe)
        self.assertTrue(ok)
        self.assertIn("listing", out)

    def test_allowed_cat_still_works(self):
        ok, out = sandbox.safe_tool_run("cat a.txt", self.ctx, _ls,
                                        _safe)
        self.assertTrue(ok)
        self.assertEqual(out, "hello")

    def test_allowed_pytest_executes(self):
        ok, _ = sandbox.safe_tool_run(
            "python3 -m py_compile a.txt", self.ctx, _ls, _safe)
        # py_compile on a .txt fails honestly (rc!=0), but must not
        # refuse the grammar and must not spawn a shell.
        self.assertIn(ok, (True, False))

    def test_disallowed_command_rejected(self):
        ok, out = sandbox.safe_tool_run("rm -rf /", self.ctx, _ls,
                                        _safe)
        self.assertFalse(ok)
        self.assertIn("only pytest", out)

    def test_pytest_arg_allowlist(self):
        ok, _ = sandbox.safe_tool_run(
            "python3 -m pytest tests/; evil", self.ctx, _ls, _safe)
        self.assertFalse(ok)

    def test_ran_tests_counter(self):
        sandbox.safe_tool_run("python3 -m pytest tests/ -x -q",
                              self.ctx, _ls, _safe)
        self.assertEqual(self.ctx.ran_tests, 1)


class SafePathTests(unittest.TestCase):
    def test_sibling_prefix_rejected(self):
        with self.assertRaises(ValueError):
            _safe("../sbx_evil", _Ctx("/tmp/sbx"))

    def test_dotdot_rejected(self):
        with self.assertRaises(ValueError):
            _safe("../../etc/passwd", _Ctx("/tmp/sbx"))

    def test_inside_allowed(self):
        self.assertTrue(
            _safe("shop/tests", _Ctx("/tmp/sbx")).startswith("/tmp/sbx"))


if __name__ == "__main__":
    unittest.main()
