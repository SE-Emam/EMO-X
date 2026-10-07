"""Sandbox execution helpers (stdlib only).

Contract refs: SPEC sections 24, 35 (sandbox, forbidden paths, timeouts).
Normalized from shared/bench_lib.py WITHOUT importing or modifying it
(bench_lib.py is legacy v1 and stays runnable).
"""

import os
import re
import shlex
import shutil
import subprocess
import tempfile


class SandboxPathEscape(ValueError):
    """Raised when a path escapes the sandbox root."""


class SandboxTimeout(TimeoutError):
    """Raised when a sandboxed command exceeds its timeout."""


FORBIDDEN_PREFIXES = ("/etc", "/root", "/home", "/var/run/secrets",
                       "/proc", "/sys", "/dev", "/var/run/docker.sock")


def _forbidden_dynamic():
    """Per-user secret dirs (fail-closed even when $HOME is unusual)."""
    home = os.path.expanduser("~")
    if not home or home == "~":
        return (os.path.expanduser("~/.aws"), os.path.expanduser("~/.ssh"))
    return (os.path.join(home, ".aws"), os.path.join(home, ".ssh"))


def create_sandbox(prefix="emox_sandbox_"):
    """Create a sandbox-only temp dir. Returns its path. SPEC 35."""
    return tempfile.mkdtemp(prefix=prefix)


def destroy_sandbox(path):
    """Remove a sandbox dir. SPEC 35."""
    shutil.rmtree(path, ignore_errors=True)


def resolve_sandbox_path(root, relpath):
    """Resolve relpath inside root; raise SandboxPathEscape on escape. SPEC 35.

    Canonicalizes via realpath (symlinks resolved) and confines with
    commonpath (not startswith), then enforces the forbidden-prefix
    denylist on the RESOLVED path. Absolute inputs are only allowed when
    already inside root.
    """
    if relpath is None:
        raise SandboxPathEscape("empty path")
    rel = str(relpath)
    if not rel.strip():
        raise SandboxPathEscape("empty path")
    root_real = os.path.realpath(root)
    if os.path.isabs(rel):
        # Absolute paths are only allowed if already inside root.
        full = os.path.realpath(os.path.normpath(rel))
    else:
        full = os.path.realpath(
            os.path.normpath(os.path.join(root_real, rel.lstrip("/"))))
    try:
        inside = (full == root_real
                  or os.path.commonpath([full, root_real]) == root_real)
    except ValueError:
        raise SandboxPathEscape("path escape: %r" % (relpath,))
    if not inside:
        raise SandboxPathEscape("path escape: %r" % (relpath,))
    for prefix in list(FORBIDDEN_PREFIXES) + list(_forbidden_dynamic()):
        resolved_prefix = os.path.realpath(prefix)
        if full == resolved_prefix or full.startswith(resolved_prefix + os.sep):
            raise SandboxPathEscape("forbidden path: %r" % (relpath,))
    return full


def _refuse_symlink(path, relpath):
    """Raise SandboxPathEscape if a lexical path is (or traverses) a symlink."""
    if os.path.islink(path):
        raise SandboxPathEscape("symlink refused: %r" % (relpath,))


def write_sandbox_file(root, relpath, content):
    """Write text content to a file inside the sandbox. SPEC 35.

    Refuses symlinked targets (O_NOFOLLOW) so a model-planted
    symlink can never redirect the write outside the sandbox.
    """
    full = resolve_sandbox_path(root, relpath)
    # Refuse symlinks on BOTH the lexical path (planted link name) and
    # the resolved path, before O_NOFOLLOW enforces it at open(2).
    root_real = os.path.realpath(root)
    lexical = os.path.normpath(os.path.join(
        root_real, str(relpath).lstrip("/")))
    _refuse_symlink(lexical, relpath)
    _refuse_symlink(full, relpath)
    parent = os.path.dirname(full) or root
    os.makedirs(parent, exist_ok=True)
    fd = os.open(full, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except BaseException:
        try:
            os.unlink(full)
        except OSError:
            pass
        raise
    return full


def _clean_env():
    """Environment for sandboxed procs: proxy-strip only (NOT net isolation).

    Strips proxy vars (plus EMOX_ALLOW_LOCAL, audit SEC-5) so a child
    cannot reach the network via ambient proxy config or inherit the
    parent's SSRF-guard bypass. This is NOT a network sandbox: direct
    sockets from model code are still possible; true isolation (net
    namespace/seccomp) is out of scope for the stdlib harness and must
    not be claimed elsewhere (SPEC 24 wording fixed accordingly).
    """
    env = dict(os.environ)
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                "ALL_PROXY", "all_proxy",
                # Audit SEC-5: never let a sandboxed child inherit the
                # SSRF-guard bypass; the parent's decision does not
                # propagate into untrusted child processes.
                "EMOX_ALLOW_LOCAL"):
        env.pop(key, None)
    env["EMOX_SANDBOX"] = "1"
    return env


def run_in_sandbox(argv, sandbox_dir=None, timeout=30, input_text=None):
    """Run argv with cwd confined to a temp sandbox dir. SPEC 35.

    Returns (returncode, output_tail). Raises SandboxTimeout on timeout.
    Hardening: cwd-confined + proxy-stripped env only; NOT full network
    or syscall isolation (see _clean_env).
    """
    own_dir = sandbox_dir is None
    root = sandbox_dir or create_sandbox()
    try:
        try:
            proc = subprocess.run(
                argv, cwd=root, capture_output=True, text=True,
                timeout=timeout, input=input_text, env=_clean_env())
        except subprocess.TimeoutExpired as e:
            raise SandboxTimeout("command timed out after %ss" % timeout) from e
        tail = (proc.stdout + proc.stderr)[-2000:]
        return proc.returncode, tail
    finally:
        if own_dir:
            destroy_sandbox(root)


def run_python_code(code, test="", timeout=30):
    """Run python code+test in a sandbox. Returns (ok, log_tail). SPEC 35."""
    rc, tail = run_in_sandbox(["python3", "-c", code + "\n" + test],
                              timeout=timeout)
    return rc == 0, tail


_SAFE_ARG_RE = re.compile(r"^[\w\-./=:+]+$")
# Audit note: '@' deliberately excluded (defense in depth; nothing
# legitimate needs it). ':' is KEPT — pytest node IDs (file::test)
# are legitimate agent usage, and shell=False already renders every
# character inert. Blindly dropping ':' would break real debugging.


def _confine_root(root):
    """Return root if it is an existing dir, else raise ValueError."""
    if not isinstance(root, str) or not os.path.isdir(root):
        raise ValueError("sandbox root is not a directory: %r" % (root,))
    return root


def safe_tool_run(cmd, ctx, ls_fn, safe_fn, timeout=120):
    """Execute one agent `run` command with NO shell. Audit fix D1.

    Closed grammar (same documented contract as before: only
    pytest/py_compile/ls/cat, so agent prompts are unchanged):
      ls [path]                 -> ls_fn(path, ctx); flags rejected
      cat <path> [<path>...]    -> file contents via safe_fn (no read-log)
      python3 -m pytest [...]   -> argv exec, args allowlisted
      python3 -m py_compile [...] -> argv exec, args allowlisted
    Anything else (including `;`, `|`, `&&`, `$()`, backticks, newlines,
    redirections) is rejected or passed as inert literal argv — it can
    never reach a shell because no shell is ever spawned. Returns
    (ok, output_tail) with the legacy error strings preserved.
    """
    text = cmd if isinstance(cmd, str) else ""
    if not text.strip():
        return False, "ERROR: only pytest/py_compile/ls/cat allowed"
    try:
        argv = shlex.split(text, posix=True)
    except ValueError:
        return False, "ERROR: only pytest/py_compile/ls/cat allowed"
    if not argv:
        return False, "ERROR: only pytest/py_compile/ls/cat allowed"
    try:
        root = _confine_root(getattr(ctx, "root", None))
    except ValueError as e:
        return False, "ERROR: %s" % e
    head = argv[0]
    if head == "ls":
        rest = argv[1:]
        if any(a.startswith("-") for a in rest):
            return False, "ERROR: ls flags not supported (path only)"
        if len(rest) > 1:
            return False, "ERROR: ls takes at most one path"
        ok, out = ls_fn(rest[0] if rest else ".", ctx)
        return ok, out
    if head == "cat":
        if len(argv) < 2:
            return False, "ERROR: cat needs a path"
        outs = []
        for p in argv[1:]:
            try:
                full = safe_fn(p, ctx)
            except ValueError:
                return False, "ERROR: path escape"
            if os.path.islink(full):
                return False, "ERROR: refusing to read symlink: %s" % p
            if not os.path.isfile(full):
                return False, "ERROR: no such file: %s" % p
            fd = os.open(full, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                with os.fdopen(fd, encoding="utf-8",
                               errors="replace") as fh:
                    data = fh.read()
            except OSError:
                return False, "ERROR: refusing to read symlink: %s" % p
            # Audit fix 1: same 6000-char cap as tool_read (memory/context
            # bound) + unified read trail (ctx.reads, AttributeError-safe
            # for minimal test doubles).
            outs.append(data[:6000] +
                        ("...[truncated]" if len(data) > 6000 else ""))
            try:
                ctx.reads.append(p)
            except AttributeError:
                pass
        return True, "\n".join(outs)
    if head == "python3" and len(argv) >= 3 and argv[1] == "-m" and \
            argv[2] in ("pytest", "py_compile"):
        rest = argv[3:]
        if not all(_SAFE_ARG_RE.match(a) for a in rest):
            return False, "ERROR: only pytest/py_compile/ls/cat allowed"
        if "pytest" in argv or any("tests" in a for a in rest):
            try:
                ctx.ran_tests += 1
            except AttributeError:
                pass
        try:
            proc = subprocess.run(
                argv, cwd=root, capture_output=True, text=True,
                timeout=timeout, env=_clean_env())
        except subprocess.TimeoutExpired:
            return False, "ERROR: command timed out after %ss" % timeout
        return (proc.returncode == 0), (proc.stdout + proc.stderr)[-2500:]
    return False, "ERROR: only pytest/py_compile/ls/cat allowed"
