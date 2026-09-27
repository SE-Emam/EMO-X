"""Shared agent-loop tool primitives (stdlib only).

Single source of truth for Ctx, _safe, tool_ls, tool_read, tool_run,
tool_edit — previously duplicated in shared/run.py and
suites/agent-loop/episode.py (audit item 4: duplicated code had
already diverged once, in the D1 import fallback). Both import from
here now, so future fixes land once.

Contract refs: SPEC P4 (trajectory), SPEC 35 (fail-closed sandbox).
Security: tool_run delegates to sandbox.safe_tool_run (NO shell,
audit fix D1); _safe uses os.path.commonpath (audit fix D2).
"""

import os
import subprocess
import tempfile


class Ctx(object):
    def __init__(self, root):
        self.root = root
        self.calls = 0
        self.failed = 0
        self.reads = []
        self.edited = set()
        self.ran_tests = 0
        self.nonexistent = 0


def _safe(p, ctx):
    full = os.path.normpath(os.path.join(ctx.root, (p or "").lstrip("/")))
    # Audit fix D2: commonpath (not startswith) — a sibling whose name
    # merely shares the prefix (e.g. /tmp/sbx_evil vs /tmp/sbx) must fail.
    # The root is rstripped so a trailing slash on ctx.root cannot cause
    # a false escape (commonpath never returns a trailing slash).
    root = (ctx.root or "").rstrip(os.sep) or os.sep
    try:
        if os.path.commonpath([full, root]) != root:
            raise ValueError("path escape")
    except ValueError:
        raise ValueError("path escape")
    return full


def tool_ls(p, ctx):
    d = _safe(p or ".", ctx)
    if not os.path.isdir(d):
        return False, "ERROR: not a directory: %s" % p
    return True, "\n".join(sorted(os.listdir(d)))


def tool_read(p, ctx):
    f = _safe(p, ctx)
    if not os.path.isfile(f):
        ctx.nonexistent += 1
        return False, "ERROR: no such file: %s" % p
    ctx.reads.append(p)
    with open(f) as fh:
        data = fh.read()
    return True, data[:6000] + ("...[truncated]" if len(data) > 6000 else "")


def tool_run(cmd, ctx):
    """Execute via sandbox.safe_tool_run (NO shell). Audit fix D1.

    Same contract as before (pytest/py_compile/ls/cat only); shell
    metacharacters are rejected or inert argv, never executed.
    """
    try:
        from sandbox import safe_tool_run
    except ImportError:
        from shared.sandbox import safe_tool_run
    return safe_tool_run(cmd, ctx, tool_ls, _safe)


def tool_edit(path, old, new, ctx):
    f = _safe(path, ctx)
    if os.path.islink(f):
        return False, "ERROR: refusing to edit symlink: %s" % path
    if not os.path.isfile(f):
        ctx.nonexistent += 1
        return False, "ERROR: no such file: %s" % path
    with open(f) as fh:
        data = fh.read()
    if old not in data:
        return False, "ERROR: `old` block not found verbatim (check whitespace)"
    new_data = data.replace(old, new, 1)
    # Re-read at write time: refuse if the file changed under us.
    with open(f) as fh:
        fresh = fh.read()
    if fresh != data:
        return False, "ERROR: file changed during edit, retry: %s" % path
    if old not in fresh:
        return False, "ERROR: `old` block not found verbatim (check whitespace)"
    new_data = fresh.replace(old, new, 1)
    # Atomic write: temp file in the same directory + os.replace, so a
    # crash never leaves a half-written target behind.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(f) or ".",
                               prefix=".edit-",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(new_data)
        os.replace(tmp, f)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    ctx.edited.add(os.path.relpath(f, ctx.root))
    return True, "OK edited %s" % path
