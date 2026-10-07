"""Tests for pip packaging (pyproject + emox shim + version lock)."""

import os
import sys
import unittest

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared"), os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class PackagingTests(unittest.TestCase):
    def test_pyproject_parses(self):
        with open(os.path.join(_ROOT, "pyproject.toml"), "rb") as f:
            data = tomllib.load(f)
        assert data["project"]["name"] == "emo-x-eval"
        assert "emo" in data["project"]["scripts"]

    def test_version_lock(self):
        """One version everywhere: pyproject == runner == MCP == skill."""
        with open(os.path.join(_ROOT, "pyproject.toml"), "rb") as f:
            pkg_version = tomllib.load(f)["project"]["version"]
        import runner as _runner

        assert pkg_version == _runner.BENCHMARK_VERSION
        import emox

        assert emox.__version__ == pkg_version
        import re

        with open(os.path.join(_ROOT, "SKILL.md"), encoding="utf-8") as skill_file:
            skill = skill_file.read()
        m = re.search(r"^version:\s*(\S+)", skill, re.M)
        assert m is not None
        assert m.group(1) == pkg_version

    def test_emox_resolves_live_tree(self):
        import emox

        root = emox.tree_root()
        assert os.path.isfile(os.path.join(root, "shared", "run.py"))
        for module in ("bundles.py", "environment.py"):
            assert os.path.isfile(os.path.join(root, "shared", module))
        assert os.path.isfile(os.path.join(root, "Dockerfile.sandbox"))

    def test_emox_lazy_api(self):
        import emox

        assert callable(emox.run_suite)
        assert callable(emox.run_self_test)
        assert callable(emox.banner)
        # Block-letter logo carries no literal "EMO-X"; tagline does.
        assert "Execution" in emox.banner(width=80, color=False)
        with pytest.raises(AttributeError):
            missing_attribute = "no_such_attribute"
            assert getattr(emox, missing_attribute)

    def test_emo_cli_version(self):
        import io
        from contextlib import redirect_stdout

        from emox import cli

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["--version"])
        assert rc == 0
        assert "2.0.0-rc1" in buf.getvalue()


if __name__ == "__main__":
    unittest.main()
