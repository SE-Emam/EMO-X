"""emox: pip-installable entry to the EMO-X benchmark tree (stdlib only).

Resolution order for the runtime tree (frozen layout, never moved):
  1. $EMOX_ROOT, if it contains shared/run.py (explicit override).
  2. emox/data/ next to this file (non-editable wheel install).
  3. Walk up from this file for a checkout containing shared/run.py
     (editable install `pip install -e .`, or in-tree use).

Once resolved, the tree's shared/ dir is put on sys.path so the
harness's own bare imports (runner, backends, scoring, ...) work
exactly as in a checkout. Public API is lazy: importing emox has no
side effects beyond path setup.
"""

import os
import sys

__version__ = "2.0.0-rc1"

#: Runtime tree dirs. Single source of truth mirrored in setup.py TREE_DIRS:
#: the wheel ships these verbatim under emox/data/. Keep both in sync.
_TREE_DIRS = (
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


def _is_tree(root):
    if not (root and os.path.isfile(os.path.join(root, "shared", "run.py"))):
        return False
    # Strict check: every shipped dir must be present so a partial wheel
    # or checkout fails fast here instead of mid-benchmark.
    return all(os.path.isdir(os.path.join(root, d)) for d in _TREE_DIRS)


def tree_root():
    """Locate the EMO-X runtime tree. Raises RuntimeError if absent."""
    env = os.environ.get("EMOX_ROOT", "")
    if _is_tree(env):
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "data")
    if _is_tree(data):
        return data
    cur = os.path.abspath(os.path.join(here, "..", ".."))
    for _ in range(4):
        if _is_tree(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    raise RuntimeError(
        "EMO-X runtime tree not found. Set EMOX_ROOT to your emo-x "
        "checkout, or reinstall the emo-x package."
    )


def _boot():
    """Put the tree on sys.path. Idempotent. Returns the tree root."""
    root = tree_root()
    # shared/ first for the harness's bare imports (runner, backends,
    # scoring, ...); root itself so generators/judges/health/adapters
    # resolve as packages (from generators.task_dsl import ...).
    for sub in ("shared", ""):
        path = os.path.join(root, sub) if sub else root
        if path not in sys.path:
            sys.path.insert(0, path)
    return root


def __getattr__(name):
    """Lazy public API: run_suite, run_profile, run_self_test,
    health_snapshot, compare_models, banner, make_chat, splash_server_info.
    """
    _boot()
    if name == "run_suite":
        from runner import run_suite

        return run_suite
    if name == "run_profile":
        from runner import run_profile

        return run_profile
    if name == "run_self_test":
        from runner import run_self_test

        return run_self_test
    if name == "health_snapshot":
        from runner import health_snapshot

        return health_snapshot
    if name == "compare_models":
        try:
            from report_v2 import compare_models
        except ImportError:
            from shared.report_v2 import compare_models
        return compare_models
    if name == "banner":
        from splash import banner

        return banner
    if name == "make_chat":
        from backends import make_chat

        return make_chat
    if name == "splash_server_info":
        from splash import banner as _banner

        return {"name": "emo-x", "version": __version__, "splash": _banner(width=80, color=False)}
    raise AttributeError("module 'emox' has no attribute %r" % (name,))
