"""Sandbox execution helpers (stdlib only).

Contract refs: SPEC sections 24, 35 (sandbox, forbidden paths, timeouts).
Normalized from shared/bench_lib.py WITHOUT importing or modifying it
(bench_lib.py is legacy v1 and stays runnable).
"""

import contextlib
import os
import re
import selectors
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from collections import deque


class SandboxPathEscape(ValueError):
    """Raised when a path escapes the sandbox root."""


class SandboxTimeout(TimeoutError):
    """Raised when a sandboxed command exceeds its timeout."""


class SandboxRuntimeUnavailable(RuntimeError):
    """Raised when the required Docker sandbox cannot be started."""


FORBIDDEN_PREFIXES = (
    "/etc",
    "/root",
    "/home",
    "/var/run/secrets",
    "/proc",
    "/sys",
    "/dev",
    "/var/run/docker.sock",
)

_SANDBOX_ENV_KEYS = frozenset(
    {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "LANG",
        "LC_ALL",
        "TZ",
        "TMP",
        "TEMP",
        "TMPDIR",
    }
)
_DOCKER_CLIENT_ENV_KEYS = (
    "PATH",
    "HOME",
    "DOCKER_HOST",
    "DOCKER_CONTEXT",
    "DOCKER_CONFIG",
    "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
    "DOCKER_API_VERSION",
)
_SANDBOX_IMAGE = "emox-sandbox:latest"
_CONTAINER_WORKDIR = "/workspace"
_SANDBOX_MEMORY = "1g"
_SANDBOX_CPUS = "2"
_SANDBOX_PIDS = "128"
_MAX_OUTPUT_BYTES = 1_048_576
_OUTPUT_TRUNCATION_MARKER = (
    "[output truncated; retained last %d bytes]\n" % _MAX_OUTPUT_BYTES
)


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
            os.path.normpath(os.path.join(root_real, rel.lstrip("/")))
        )
    try:
        inside = full == root_real or os.path.commonpath([full, root_real]) == root_real
    except ValueError:
        raise SandboxPathEscape(f"path escape: {relpath!r}")
    if not inside:
        raise SandboxPathEscape(f"path escape: {relpath!r}")
    for prefix in list(FORBIDDEN_PREFIXES) + list(_forbidden_dynamic()):
        resolved_prefix = os.path.realpath(prefix)
        if full == resolved_prefix or full.startswith(resolved_prefix + os.sep):
            raise SandboxPathEscape(f"forbidden path: {relpath!r}")
    return full


def _refuse_symlink(path, relpath):
    """Raise SandboxPathEscape if a lexical path is (or traverses) a symlink."""
    if os.path.islink(path):
        raise SandboxPathEscape(f"symlink refused: {relpath!r}")


def write_sandbox_file(root, relpath, content):
    """Write text content to a file inside the sandbox. SPEC 35.

    Refuses symlinked targets (O_NOFOLLOW) so a model-planted
    symlink can never redirect the write outside the sandbox.
    """
    full = resolve_sandbox_path(root, relpath)
    # Refuse symlinks on BOTH the lexical path (planted link name) and
    # the resolved path, before O_NOFOLLOW enforces it at open(2).
    root_real = os.path.realpath(root)
    lexical = os.path.normpath(os.path.join(root_real, str(relpath).lstrip("/")))
    _refuse_symlink(lexical, relpath)
    _refuse_symlink(full, relpath)
    parent = os.path.dirname(full) or root
    os.makedirs(parent, exist_ok=True)
    fd = os.open(full, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(full)
        raise
    return full


def _clean_env():
    """Return a minimal environment for compatibility callers.

    Docker-backed execution does not inherit this environment; the
    container receives only fixed HOME and TMPDIR settings.
    """
    env = {}
    for key in _SANDBOX_ENV_KEYS:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    env.setdefault("PATH", os.defpath)
    env["EMOX_SANDBOX"] = "1"
    return env


def _docker_client_env():
    """Environment for the trusted Docker client, never passed to the container."""
    env = {}
    for key in _DOCKER_CLIENT_ENV_KEYS:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    env.setdefault("PATH", os.defpath)
    return env


def _container_args(argv, root):
    """Translate host paths inside the bound workdir to container paths."""
    translated = []
    for arg in argv:
        text = str(arg)
        if os.path.isabs(text):
            full = os.path.realpath(text)
            try:
                if os.path.commonpath([full, root]) == root:
                    relative = os.path.relpath(full, root)
                    text = (
                        _CONTAINER_WORKDIR
                        if relative == "."
                        else os.path.join(_CONTAINER_WORKDIR, relative)
                    )
            except ValueError:
                pass
        translated.append(text)
    return translated


def _stop_container(docker, name, env):
    """Kill a container whose Docker client timed out."""
    proc = subprocess.run(
        [docker, "kill", name], capture_output=True, text=True, timeout=10, env=env
    )
    if proc.returncode == 0 or "No such container" in proc.stderr:
        return
    raise SandboxRuntimeUnavailable(
        f"unable to stop timed-out sandbox container: {(proc.stderr or proc.stdout)[-500:]}"
    )


def run_in_sandbox(argv, sandbox_dir=None, timeout=30, input_text=None):
    """Run argv in a networkless, read-only Docker sandbox. SPEC 35.

    Only the dedicated temporary work directory is mounted read/write.
    The container has no network, no Linux capabilities, and a read-only
    root filesystem. CPU, memory, PID count, and retained output are
    capped. Returns (returncode, output_tail).
    """
    own_dir = sandbox_dir is None
    root = sandbox_dir or create_sandbox()
    root = os.path.realpath(root)
    temp_root = os.path.realpath(tempfile.gettempdir())
    try:
        confined = (
            root != temp_root and os.path.commonpath([root, temp_root]) == temp_root
        )
    except ValueError:
        confined = False
    if not os.path.isdir(root) or not confined:
        if own_dir:
            destroy_sandbox(root)
        raise SandboxPathEscape("sandbox directory must be a dedicated temp dir")
    if "," in root:
        if own_dir:
            destroy_sandbox(root)
        raise SandboxPathEscape("sandbox path contains a Docker mount delimiter")
    os.makedirs(os.path.join(root, ".emox-tmp"), mode=0o700, exist_ok=True)
    os.makedirs(os.path.join(root, ".emox-home"), mode=0o700, exist_ok=True)
    env = _docker_client_env()
    docker = shutil.which("docker", path=env["PATH"])
    if docker is None:
        if own_dir:
            destroy_sandbox(root)
        raise SandboxRuntimeUnavailable("Docker CLI not found")
    name = "emox-sandbox-" + uuid.uuid4().hex
    image = os.environ.get("EMOX_SANDBOX_IMAGE", _SANDBOX_IMAGE)
    if not re.fullmatch(r"[a-z0-9][a-z0-9._:/@-]*", image):
        if own_dir:
            destroy_sandbox(root)
        raise ValueError("invalid EMOX_SANDBOX_IMAGE")
    uid = str(os.getuid()) if hasattr(os, "getuid") else "65534"
    gid = str(os.getgid()) if hasattr(os, "getgid") else "65534"
    command = [docker, "run"]
    if input_text is not None:
        command.append("--interactive")
    command += [
        "--rm",
        "--init",
        "--name",
        name,
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        f"--memory={_SANDBOX_MEMORY}",
        f"--memory-swap={_SANDBOX_MEMORY}",
        f"--cpus={_SANDBOX_CPUS}",
        f"--pids-limit={_SANDBOX_PIDS}",
        "--user",
        uid + ":" + gid,
        "--env",
        "HOME=/workspace/.emox-home",
        "--env",
        "TMPDIR=/workspace/.emox-tmp",
        "--workdir",
        _CONTAINER_WORKDIR,
        "--mount",
        f"type=bind,src={root},dst={_CONTAINER_WORKDIR}",
        image,
    ] + _container_args(argv, root)
    proc = None
    try:
        proc = subprocess.Popen(
            command,
            cwd=temp_root,
            stdin=(subprocess.PIPE if input_text is not None else subprocess.DEVNULL),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            env=env,
        )
        stdout = proc.stdout
        stdin = proc.stdin
        if stdout is None:
            raise SandboxRuntimeUnavailable(
                "Docker sandbox output stream was not created"
            )
        output: deque[bytes] = deque()
        output_size = 0
        truncated = False
        input_bytes = input_text.encode("utf-8") if input_text is not None else b""
        input_offset = 0
        output_open = True
        selector = selectors.DefaultSelector()
        selector.register(stdout.fileno(), selectors.EVENT_READ, "output")
        if stdin is not None:
            if input_bytes:
                os.set_blocking(stdin.fileno(), False)
                selector.register(stdin.fileno(), selectors.EVENT_WRITE, "input")
            else:
                stdin.close()
        deadline = time.monotonic() + timeout
        try:
            while output_open or proc.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _stop_container(docker, name, env)
                    raise SandboxTimeout(f"command timed out after {timeout}s")
                for key, _ in selector.select(min(remaining, 0.1)):
                    if key.data == "input":
                        if stdin is None:
                            raise SandboxRuntimeUnavailable(
                                "Docker sandbox input stream was not created"
                            )
                        try:
                            written = os.write(
                                key.fd, input_bytes[input_offset : input_offset + 65536]
                            )
                        except BlockingIOError:
                            continue
                        except BrokenPipeError:
                            written = len(input_bytes) - input_offset
                        input_offset += written
                        if input_offset >= len(input_bytes):
                            selector.unregister(key.fd)
                            stdin.close()
                    else:
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fd)
                            stdout.close()
                            output_open = False
                            continue
                        truncated = (
                            truncated or output_size + len(chunk) > _MAX_OUTPUT_BYTES
                        )
                        output.append(chunk)
                        output_size += len(chunk)
                        while output_size > _MAX_OUTPUT_BYTES:
                            excess = output_size - _MAX_OUTPUT_BYTES
                            if excess >= len(output[0]):
                                output_size -= len(output.popleft())
                            else:
                                output[0] = output[0][excess:]
                                output_size -= excess
            returncode = proc.wait()
        finally:
            selector.close()
            if stdin is not None and not stdin.closed:
                stdin.close()
            if not stdout.closed:
                stdout.close()
        output_text = b"".join(output).decode("utf-8", errors="replace")
        if truncated:
            output_text = _OUTPUT_TRUNCATION_MARKER + output_text
        if returncode == 125:
            raise SandboxRuntimeUnavailable(
                f"Docker could not start the sandbox: {output_text[-500:]}"
            )
        return returncode, output_text
    except SandboxTimeout:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait()
        raise
    except OSError as e:
        if proc is None:
            raise SandboxRuntimeUnavailable(
                f"unable to start Docker sandbox: {e}"
            ) from e
        raise
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait()
        if own_dir:
            destroy_sandbox(root)


def run_python_code(code, test="", timeout=30):
    """Run python code+test in a sandbox. Returns (ok, log_tail). SPEC 35."""
    rc, tail = run_in_sandbox(["python3", "-c", code + "\n" + test], timeout=timeout)
    return rc == 0, tail


_SAFE_ARG_RE = re.compile(r"^[\w\-./=:+]+$")
# Audit note: '@' deliberately excluded (defense in depth; nothing
# legitimate needs it). ':' is KEPT — pytest node IDs (file::test)
# are legitimate agent usage, and shell=False already renders every
# character inert. Blindly dropping ':' would break real debugging.


def _confine_root(root):
    """Return root if it is an existing dir, else raise ValueError."""
    if not isinstance(root, str) or not os.path.isdir(root):
        raise ValueError(f"sandbox root is not a directory: {root!r}")
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
        return False, f"ERROR: {e}"
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
                return False, f"ERROR: refusing to read symlink: {p}"
            if not os.path.isfile(full):
                return False, f"ERROR: no such file: {p}"
            fd = os.open(full, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                with os.fdopen(fd, encoding="utf-8", errors="replace") as fh:
                    data = fh.read()
            except OSError:
                return False, f"ERROR: refusing to read symlink: {p}"
            # Audit fix 1: same 6000-char cap as tool_read (memory/context
            # bound) + unified read trail (ctx.reads, AttributeError-safe
            # for minimal test doubles).
            outs.append(data[:6000] + ("...[truncated]" if len(data) > 6000 else ""))
            with contextlib.suppress(AttributeError):
                ctx.reads.append(p)
        return True, "\n".join(outs)
    if (
        head == "python3"
        and len(argv) >= 3
        and argv[1] == "-m"
        and argv[2] in ("pytest", "py_compile")
    ):
        rest = argv[3:]
        if not all(_SAFE_ARG_RE.match(a) for a in rest):
            return False, "ERROR: only pytest/py_compile/ls/cat allowed"
        if "pytest" in argv or any("tests" in a for a in rest):
            with contextlib.suppress(AttributeError):
                ctx.ran_tests += 1
        try:
            rc, output = run_in_sandbox(argv, sandbox_dir=root, timeout=timeout)
        except SandboxTimeout:
            return False, f"ERROR: command timed out after {timeout}s"
        return rc == 0, output[-2500:]
    return False, "ERROR: only pytest/py_compile/ls/cat allowed"
