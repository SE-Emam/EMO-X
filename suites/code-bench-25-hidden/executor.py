"""Executor alias for suites/code-bench-25-hidden (B58 hash pattern).

All execution logic lives in cases.py; this module exposes the
prompt_pack_sha256/harness_sha256 pair (B58) bound to THIS file's bytes
so any prompt/glue change invalidates hashes.

Gate contract (for Y-INT): run_family() requires the caller to pass
scope="hidden-ok" (the --hidden-ok CLI opt-in). Any other value raises
ScopeRequiredError and no model call is made.

Basename isolation: sibling cases.py is loaded by file path (never bare
``import cases``) because every suite ships a cases.py and bare imports
collide in sys.modules when several suites run in one process.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

#: Opt-in scope string Y-INT passes through from --hidden-ok.
HIDDEN_SCOPE = "hidden-ok"


class ScopeRequiredError(PermissionError):
    """Raised when a hidden run is attempted without the opt-in scope."""


def _load_cases():
    path = os.path.join(HERE, "cases.py")
    name = "emox_hidden_cases"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_cases = _load_cases()
SUITE = _cases.SUITE
FAMILY_IDS = _cases.FAMILY_IDS
HIDDEN_VARIANT = _cases.HIDDEN_VARIANT
make_instance = _cases.make_instance
check_family = _cases.check_family
prompt_messages = _cases.prompt_messages
prompt_text = _cases.prompt_text
load_manifest = _cases.load_manifest
prompt_pack_sha256 = _cases.prompt_pack_sha256

from shared.manifests import sha256_bytes  # noqa: E402


def require_hidden_scope(scope):
    """Raise ScopeRequiredError unless scope is the hidden opt-in."""
    if scope != HIDDEN_SCOPE:
        raise ScopeRequiredError(
            "hidden suite requires scope=%r (pass --hidden-ok)" % (HIDDEN_SCOPE,)
        )


def run_family(family, chat, run_id, model_id, trial_id=1, index=1, seed=0, scope=None, **kwargs):
    """Run one hidden instance. Gate: scope must be "hidden-ok"."""
    require_hidden_scope(scope)
    return _cases.run_family(
        family, chat, run_id, model_id, trial_id=trial_id, index=index, seed=seed, **kwargs
    )


def harness_sha256():
    """SHA256 of this executor file's bytes (for run manifest)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
