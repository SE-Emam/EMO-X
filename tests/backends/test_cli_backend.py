"""Tests for the cli backend (local agent-CLI subprocess)."""

import os
import subprocess
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import backends


class CliBackendTests(unittest.TestCase):
    def _ok(self, stdout="\x1b[0m\n> build · m\nHello\n"):
        proc = mock.Mock()
        proc.returncode = 0
        proc.stdout = stdout
        proc.stderr = ""
        return proc

    def test_strips_ansi_and_status_lines(self):
        with mock.patch.object(subprocess, "run",
                               return_value=self._ok()) as run:
            text, secs, usage = backends.chat_cli(
                [{"role": "user", "content": "hi"}], "opencode",
                "opencode/m")
            self.assertEqual(text, "Hello")
            self.assertEqual(usage, {})
            argv = run.call_args[0][0]
            self.assertIsInstance(argv, list)
            self.assertIn("--model", argv)

    def test_no_shell_used(self):
        with mock.patch.object(subprocess, "run",
                               return_value=self._ok()) as run:
            backends.chat_cli([{"role": "user", "content": "hi"}],
                              "opencode", "m")
            _, kwargs = run.call_args
            self.assertNotIn("shell", kwargs)

    def test_timeout_raises(self):
        with mock.patch.object(
                subprocess, "run",
                side_effect=subprocess.TimeoutExpired("x", 1)):
            with self.assertRaises(RuntimeError):
                backends.chat_cli([{"role": "user", "content": "hi"}],
                                  "opencode", "m")

    def test_nonzero_exit_raises(self):
        proc = mock.Mock()
        proc.returncode = 1
        proc.stdout, proc.stderr = "", "API key expired."
        with mock.patch.object(subprocess, "run", return_value=proc):
            with self.assertRaises(RuntimeError):
                backends.chat_cli([{"role": "user", "content": "hi"}],
                                  "opencode", "m")

    def test_missing_binary_raises(self):
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                backends.chat_cli([{"role": "user", "content": "hi"}],
                                  "no-such-bin-xyz", "m")

    def test_resolve_and_manifest(self):
        name, base, mod, key = backends.resolve_config(
            "cli", "/bin/echo", "opencode/m", None)
        self.assertEqual(name, "cli")
        self.assertIsNone(key)
        man = backends.get_capability_manifest("cli")
        self.assertEqual(man["seed"], "unsupported")
        self.assertEqual(man["token_usage"], "unknown")

    def test_make_chat_cli_smoke(self):
        chat = backends.make_chat("cli", "/bin/echo",
                                  "opencode/m", None)
        with mock.patch.object(subprocess, "run",
                               return_value=self._ok("World\n")):
            text, _, _ = chat([{"role": "user", "content": "hi"}])
            self.assertEqual(text, "World")


if __name__ == "__main__":
    unittest.main()
