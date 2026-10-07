"""Tests for shared/sandbox.py and shared/safety.py (stdlib). SPEC 24, 35."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import pytest
import safety
import sandbox


class TestSandbox(unittest.TestCase):
    def test_create_and_destroy(self):
        root = sandbox.create_sandbox()
        assert os.path.isdir(root)
        sandbox.destroy_sandbox(root)
        assert not os.path.exists(root)

    def test_blocks_path_escape(self):
        root = sandbox.create_sandbox()
        try:
            with pytest.raises(sandbox.SandboxPathEscape):
                sandbox.resolve_sandbox_path(root, "../../etc/passwd")
            with pytest.raises(sandbox.SandboxPathEscape):
                sandbox.resolve_sandbox_path(root, "/etc/passwd")
        finally:
            sandbox.destroy_sandbox(root)

    def test_write_inside_ok(self):
        root = sandbox.create_sandbox()
        try:
            path = sandbox.write_sandbox_file(root, "sub/a.txt", "hi")
            with open(path) as f:
                assert f.read() == "hi"
        finally:
            sandbox.destroy_sandbox(root)

    def test_run_echo(self):
        rc, out = sandbox.run_in_sandbox(["echo", "hello"], timeout=10)
        assert rc == 0
        assert "hello" in out

    def test_timeout(self):
        with pytest.raises(sandbox.SandboxTimeout):
            sandbox.run_in_sandbox(["python3", "-c", "import time; time.sleep(30)"], timeout=1)

    def test_run_python_code(self):
        sensitive = {
            "OPENAI_API_KEY": "key-sentinel",
            "AWS_SECRET_ACCESS_KEY": "secret-sentinel",
            "CUSTOM_TOKEN": "token-sentinel",
            "DB_PASSWORD": "password-sentinel",
            "SERVICE_CREDENTIAL": "credential-sentinel",
        }
        with patch.dict(os.environ, sensitive):
            ok, output = sandbox.run_python_code("import os; print(os.environ)")
        assert ok, output
        for key, value in sensitive.items():
            assert key not in output
            assert value not in output

    def test_generated_code_cannot_access_unmounted_host_file(self):
        fd, host_path = tempfile.mkstemp(prefix="emox-host-only-")
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write("host-only-sentinel")
            code = (
                "try:\n"
                f"    open({host_path!r}).read()\n"
                "except (FileNotFoundError, PermissionError):\n"
                "    print('HOST_FILE_BLOCKED')\n"
                "else:\n"
                "    raise AssertionError('host file was readable')\n"
            )
            ok, output = sandbox.run_python_code(code, timeout=10)
            assert ok, output
            assert "HOST_FILE_BLOCKED" in output
        finally:
            os.unlink(host_path)

    def test_generated_code_has_no_network_egress(self):
        code = (
            "import socket\n"
            "try:\n"
            "    socket.create_connection(('1.1.1.1', 80), timeout=2)\n"
            "except OSError:\n"
            "    print('NETWORK_BLOCKED')\n"
            "else:\n"
            "    raise AssertionError('network egress was available')\n"
        )
        ok, output = sandbox.run_python_code(code, timeout=10)
        assert ok, output
        assert "NETWORK_BLOCKED" in output

    def test_container_has_hard_resource_ceilings(self):
        code = (
            "from pathlib import Path\n"
            "c = Path('/sys/fs/cgroup')\n"
            "print((c / 'memory.max').read_text().strip())\n"
            "print((c / 'cpu.max').read_text().strip())\n"
            "print((c / 'pids.max').read_text().strip())\n"
        )
        ok, output = sandbox.run_python_code(code, timeout=10)
        assert ok, output
        memory, cpu, pids = output.splitlines()
        assert int(memory) <= 1024**3
        quota, period = (int(part) for part in cpu.split())
        assert quota <= 2 * period
        assert int(pids) <= 128

    def test_output_stream_retains_only_bounded_tail(self):
        code = "print('PREFIX_SENTINEL')\nprint('x' * (2 * 1024 * 1024))\nprint('TAIL_SENTINEL')\n"
        ok, output = sandbox.run_python_code(code, timeout=10)
        assert ok, output[-200:]
        assert sandbox._OUTPUT_TRUNCATION_MARKER in output
        assert "PREFIX_SENTINEL" not in output
        assert "TAIL_SENTINEL" in output
        assert len(output) <= sandbox._MAX_OUTPUT_BYTES + len(sandbox._OUTPUT_TRUNCATION_MARKER)


class TestSandboxP04(unittest.TestCase):
    """P0-4: symlink/realpath/denylist hardening (fail-closed)."""

    def test_proc_sys_dev_forbidden(self):
        root = sandbox.create_sandbox()
        try:
            for p in (
                "/proc/self/environ",
                "/sys/kernel",
                "/dev/null",
                "/var/run/docker.sock",
            ):
                with self.assertRaises(sandbox.SandboxPathEscape, msg=p):
                    sandbox.resolve_sandbox_path(root, p)
        finally:
            sandbox.destroy_sandbox(root)

    def test_symlink_inside_root_cannot_escape(self):
        root = sandbox.create_sandbox()
        try:
            outside = os.path.join(root, "outside.txt")
            with open(outside, "w") as f:
                f.write("secret")
            link = os.path.join(root, "link.txt")
            os.symlink(outside, link)
            # Resolved path stays inside root (no escape), but direct
            # symlink read/write is refused at the call sites.
            with pytest.raises(sandbox.SandboxPathEscape):
                sandbox.write_sandbox_file(root, "link.txt", "evil")
        finally:
            sandbox.destroy_sandbox(root)

    def test_write_refuses_symlink_target(self):
        root = sandbox.create_sandbox()
        try:
            real = os.path.join(root, "real.txt")
            with open(real, "w") as f:
                f.write("orig")
            link = os.path.join(root, "w.txt")
            os.symlink(real, link)
            with pytest.raises(sandbox.SandboxPathEscape):
                sandbox.write_sandbox_file(root, "w.txt", "evil")
            with open(real) as f:
                assert f.read() == "orig"
        finally:
            sandbox.destroy_sandbox(root)

    def test_clean_env_strips_proxy_and_local_bypass(self):
        with patch.dict(
            os.environ,
            {
                "EMOX_ALLOW_LOCAL": "1",
                "http_proxy": "http://proxy.invalid",
                "OPENAI_API_KEY": "x",
                "AWS_SECRET_ACCESS_KEY": "x",
                "CUSTOM_TOKEN": "x",
                "DB_PASSWORD": "x",
                "SERVICE_CREDENTIAL": "x",
            },
        ):
            env = sandbox._clean_env()
        assert "EMOX_ALLOW_LOCAL" not in env
        assert "http_proxy" not in env
        assert "OPENAI_API_KEY" not in env
        assert "AWS_SECRET_ACCESS_KEY" not in env
        assert "CUSTOM_TOKEN" not in env
        assert "DB_PASSWORD" not in env
        assert "SERVICE_CREDENTIAL" not in env
        assert "PATH" in env
        assert env.get("EMOX_SANDBOX") == "1"


class TestSafety(unittest.TestCase):
    def test_synthetic_flag(self):
        assert safety.is_synthetic_flag("flag EMO{SYNTH_x-1} here")
        assert not safety.is_synthetic_flag("real-looking secret")

    def test_assert_synthetic_only(self):
        safety.assert_synthetic_only("EMO{SYNTH_demo}")
        with pytest.raises(ValueError):
            safety.assert_synthetic_only("no marker")

    def test_scope_gate_fail_closed(self):
        allowed, _ = safety.check_scope_gate({"approved": True, "target": "synthetic:ctf-mini"})
        assert allowed
        denied, _ = safety.check_scope_gate({"approved": True, "target": "https://real.example"})
        assert not denied
        denied2, _ = safety.check_scope_gate({})
        assert not denied2
        denied3, _ = safety.check_scope_gate(None)
        assert not denied3

    def test_fixture_validation(self):
        fix = {
            "content": "task EMO{SYNTH_case-1}",
            "offline": True,
            "sandbox_only": True,
        }
        assert safety.validate_security_fixture(fix)
        bad = dict(fix, offline=False)
        with pytest.raises(ValueError):
            safety.validate_security_fixture(bad)


if __name__ == "__main__":
    unittest.main()
