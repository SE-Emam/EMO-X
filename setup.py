"""setup.py: build-time tree bundling for the emo-x wheel.

The repo layout is frozen (prompts/hashes must stay valid), so the
wheel ships the runtime tree verbatim under emox/data/ via a build_py
hook. Editable installs (`pip install -e .`) resolve the live checkout
instead — see emox.tree_root(). stdlib only.
"""

import os
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py

TREE_DIRS = (
    "shared",
    "suites",
    "prompts",
    "generators",
    "judges",
    "health",
    "adapters",
    "mcp-server",
    "commands",
)
# NOTE: keep in sync with src/emox/__init__.py _TREE_DIRS (single source
# of truth for the runtime tree; _is_tree() validates all of these).
TREE_FILES = (
    "SKILL.md",
    "LICENSE",
    "README.md",
    "SPEC.md",
    "DENOMINATORS.md",
    "REPORT_TEMPLATE.md",
    "Dockerfile.sandbox",
)
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store")


class BuildPyWithData(build_py):
    """Copy the runtime tree into emox/data/ before packaging."""

    def run(self):
        super().run()
        src_root = os.path.abspath(os.path.dirname(__file__))
        dest = os.path.join(self.build_lib, "emox", "data")
        # Clean slate: never ship stale files from a previous build.
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest, exist_ok=True)
        for dirname in TREE_DIRS:
            src = os.path.join(src_root, dirname)
            if os.path.isdir(src):
                shutil.copytree(
                    src, os.path.join(dest, dirname), ignore=IGNORE, dirs_exist_ok=True
                )
        for filename in TREE_FILES:
            src = os.path.join(src_root, filename)
            if os.path.isfile(src):
                shutil.copy2(src, dest)


setup(cmdclass={"build_py": BuildPyWithData})
