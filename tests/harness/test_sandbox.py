"""Tests for shared/sandbox.py and shared/safety.py (stdlib). SPEC 24, 35."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import sandbox
import safety


class TestSandbox(unittest.TestCase):
    def test_create_and_destroy(self):
        root = sandbox.create_sandbox()
        self.assertTrue(os.path.isdir(root))
        sandbox.destroy_sandbox(root)
        self.assertFalse(os.path.exists(root))

    def test_blocks_path_escape(self):
        root = sandbox.create_sandbox()
        try:
            with self.assertRaises(sandbox.SandboxPathEscape):
                sandbox.resolve_sandbox_path(root, "../../etc/passwd")
            with self.assertRaises(sandbox.SandboxPathEscape):
                sandbox.resolve_sandbox_path(root, "/etc/passwd")
        finally:
            sandbox.destroy_sandbox(root)

    def test_write_inside_ok(self):
        root = sandbox.create_sandbox()
        try:
            path = sandbox.write_sandbox_file(root, "sub/a.txt", "hi")
            with open(path) as f:
                self.assertEqual(f.read(), "hi")
        finally:
            sandbox.destroy_sandbox(root)

    def test_run_echo(self):
        rc, out = sandbox.run_in_sandbox(["echo", "hello"], timeout=10)
        self.assertEqual(rc, 0)
        self.assertIn("hello", out)

    def test_timeout(self):
        with self.assertRaises(sandbox.SandboxTimeout):
            sandbox.run_in_sandbox(
                ["python3", "-c", "import time; time.sleep(30)"],
                timeout=1)

    def test_run_python_code(self):
        ok, log = sandbox.run_python_code("x = 1", "assert x == 1")
        self.assertTrue(ok)


class TestSandboxP04(unittest.TestCase):
    """P0-4: symlink/realpath/denylist hardening (fail-closed)."""

    def test_proc_sys_dev_forbidden(self):
        root = sandbox.create_sandbox()
        try:
            for p in ("/proc/self/environ", "/sys/kernel",
                      "/dev/null", "/var/run/docker.sock"):
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
            with self.assertRaises(sandbox.SandboxPathEscape):
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
            with self.assertRaises(sandbox.SandboxPathEscape):
                sandbox.write_sandbox_file(root, "w.txt", "evil")
            with open(real) as f:
                self.assertEqual(f.read(), "orig")
        finally:
            sandbox.destroy_sandbox(root)

    def test_clean_env_strips_proxy_and_local_bypass(self):
        os.environ["EMOX_ALLOW_LOCAL"] = "1"
        os.environ["http_proxy"] = "http://proxy/x"
        try:
            env = sandbox._clean_env()
        finally:
            del os.environ["EMOX_ALLOW_LOCAL"]
            del os.environ["http_proxy"]
        self.assertNotIn("EMOX_ALLOW_LOCAL", env)
        self.assertNotIn("http_proxy", env)
        self.assertEqual(env.get("EMOX_SANDBOX"), "1")


class TestSafety(unittest.TestCase):
    def test_synthetic_flag(self):
        self.assertTrue(safety.is_synthetic_flag("flag EMO{SYNTH_x-1} here"))
        self.assertFalse(safety.is_synthetic_flag("real-looking secret"))

    def test_assert_synthetic_only(self):
        safety.assert_synthetic_only("EMO{SYNTH_demo}")
        with self.assertRaises(ValueError):
            safety.assert_synthetic_only("no marker")

    def test_scope_gate_fail_closed(self):
        allowed, _ = safety.check_scope_gate({"approved": True,
                                              "target": "synthetic:ctf-mini"})
        self.assertTrue(allowed)
        denied, _ = safety.check_scope_gate({"approved": True,
                                             "target": "https://real.example"})
        self.assertFalse(denied)
        denied2, _ = safety.check_scope_gate({})
        self.assertFalse(denied2)
        denied3, _ = safety.check_scope_gate(None)
        self.assertFalse(denied3)

    def test_fixture_validation(self):
        fix = {"content": "task EMO{SYNTH_case-1}", "offline": True,
               "sandbox_only": True}
        self.assertTrue(safety.validate_security_fixture(fix))
        bad = dict(fix, offline=False)
        with self.assertRaises(ValueError):
            safety.validate_security_fixture(bad)


if __name__ == "__main__":
    unittest.main()
