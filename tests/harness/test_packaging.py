"""Tests for pip packaging (pyproject + emox shim + version lock)."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared"),
           os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class PackagingTests(unittest.TestCase):
    def test_pyproject_parses(self):
        import tomllib
        with open(os.path.join(_ROOT, "pyproject.toml"), "rb") as f:
            data = tomllib.load(f)
        self.assertEqual(data["project"]["name"], "emo-x")
        self.assertIn("emo", data["project"]["scripts"])

    def test_version_lock(self):
        """One version everywhere: pyproject == runner == MCP == skill."""
        import tomllib
        with open(os.path.join(_ROOT, "pyproject.toml"), "rb") as f:
            pkg_version = tomllib.load(f)["project"]["version"]
        import runner as _runner
        self.assertEqual(pkg_version, _runner.BENCHMARK_VERSION)
        import emox
        self.assertEqual(emox.__version__, pkg_version)
        import re
        skill = open(os.path.join(_ROOT, "SKILL.md"),
                     encoding="utf-8").read()
        m = re.search(r"^version:\s*(\S+)", skill, re.M)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), pkg_version)

    def test_emox_resolves_live_tree(self):
        import emox
        root = emox.tree_root()
        self.assertTrue(os.path.isfile(
            os.path.join(root, "shared", "run.py")))

    def test_emox_lazy_api(self):
        import emox
        self.assertTrue(callable(emox.run_suite))
        self.assertTrue(callable(emox.run_self_test))
        self.assertTrue(callable(emox.banner))
        # Block-letter logo carries no literal "EMO-X"; tagline does.
        self.assertIn("Execution", emox.banner(width=80, color=False))
        with self.assertRaises(AttributeError):
            emox.no_such_attribute

    def test_emo_cli_version(self):
        import io
        from contextlib import redirect_stdout
        from emox import cli
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["--version"])
        self.assertEqual(rc, 0)
        self.assertIn("2.0.0-rc1", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
