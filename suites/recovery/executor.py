"""Executor alias for suites/recovery (B58 hash pattern).

All execution logic lives in cases.py; this module exposes the
prompt_pack_sha256/harness_sha256 pair (B58) bound to THIS file's bytes
so any prompt/glue change invalidates hashes.

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


def _load_cases():
    path = os.path.join(HERE, "cases.py")
    name = "emox_recovery_cases"
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
FAULTS = _cases.FAULTS
make_instance = _cases.make_instance
run_family = _cases.run_family
check_family = _cases.check_family
prompt_messages = _cases.prompt_messages
prompt_text = _cases.prompt_text
load_manifest = _cases.load_manifest
prompt_pack_sha256 = _cases.prompt_pack_sha256
prompt_pack_sha256 = _cases.prompt_pack_sha256

from shared.manifests import sha256_bytes  # noqa: E402


def harness_sha256():
    """SHA256 of this executor file's bytes (for run manifest)."""
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_bytes(f.read())
