"""Tests for adapters/generic_cli_adapter.py (CLI-driven agents)."""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ADAPTERS = os.path.join(ROOT, "adapters")
for _p in (ADAPTERS,):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


GEN = _load("generic_cli_under_test", os.path.join(ADAPTERS, "generic_cli_adapter.py"))


def _fresh():
    GEN._config["bin"] = None
    GEN._config["argv_template"] = None
    for k in ("GENERIC_CLI_BIN", "GENERIC_CLI_ARGV"):
        os.environ.pop(k, None)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        _fresh()

    def test_unconfigured_fails_closed(self):
        cap = GEN.probe()
        self.assertFalse(cap["ok"])
        self.assertIn("error", cap)

    def test_missing_placeholder_rejected(self):
        GEN.configure("/bin/echo", "run --model {model}")
        cap = GEN.probe()
        self.assertFalse(cap["ok"])
        self.assertIn("{prompt}", cap["error"])

    def test_missing_binary_rejected(self):
        GEN.configure("/no/such/bin-xyz", "run {prompt}")
        cap = GEN.probe()
        self.assertFalse(cap["ok"])

    def test_env_configures(self):
        os.environ["GENERIC_CLI_BIN"] = "/bin/echo"
        os.environ["GENERIC_CLI_ARGV"] = "run {prompt}"
        try:
            self.assertTrue(GEN.probe()["ok"])
        finally:
            _fresh()


class DriveTests(unittest.TestCase):
    def setUp(self):
        _fresh()

    def test_echo_drive(self):
        GEN.configure("/bin/echo", '--model {model} "{prompt}"')
        trace = GEN.run_episode("/tmp", "fake-model", timeout_s=30)
        self.assertEqual(trace["adapter"], "generic-cli")
        self.assertTrue(trace["stopped_cleanly"])
        self.assertTrue(trace["comparability"].startswith("NON-COMPARABLE"))
        self.assertIn("cli_argv_template", trace["harness"])

    def test_run_episode_unconfigured_raises(self):
        with self.assertRaises(RuntimeError):
            GEN.run_episode("/tmp", "m", timeout_s=5)

    def test_quoting_keeps_prompt_whole(self):
        argv = GEN._build_argv(
            {"bin": "/bin/echo", "template": 'run --model {model} "{prompt}"'}, "m", "/tmp"
        )
        self.assertIn(GEN.GENERIC_TASK, argv)
        self.assertEqual(argv[0], "run")


if __name__ == "__main__":
    unittest.main()
