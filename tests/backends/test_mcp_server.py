"""Tests for the MCP server (protocol + tools + fail-closed gates)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
SERVER = os.path.join(_ROOT, "mcp-server", "server.py")
sys.path.insert(0, os.path.join(_ROOT, "mcp-server"))

import server as mcp  # noqa: E402


def call(name, arguments=None, req_id=1):
    return mcp.handle_message(
        {"jsonrpc": "2.0", "id": req_id, "method": "tools/call",
         "params": {"name": name, "arguments": arguments or {}}})


class MCPProtocolTests(unittest.TestCase):
    def test_initialize(self):
        r = mcp.handle_message({"jsonrpc": "2.0", "id": 1,
                                "method": "initialize"})
        self.assertEqual(r["result"]["serverInfo"]["name"], "emo-x")

    def test_tools_list_five(self):
        r = mcp.handle_message({"jsonrpc": "2.0", "id": 1,
                                "method": "tools/list"})
        names = sorted(t["name"] for t in r["result"]["tools"])
        self.assertEqual(names, ["compare_models", "health", "render_report",
                                 "run_profile", "run_suite", "self_test"])

    def test_unknown_method(self):
        r = mcp.handle_message({"jsonrpc": "2.0", "id": 1,
                                "method": "nope"})
        self.assertEqual(r["error"]["code"], -32601)

    def test_unknown_tool(self):
        r = call("nope")
        self.assertEqual(r["error"]["code"], -32602)

    def test_notifications_no_response(self):
        self.assertIsNone(mcp.handle_message(
            {"jsonrpc": "2.0", "method": "notifications/cancelled"}))


class MCPToolTests(unittest.TestCase):
    def test_self_test_passes(self):
        r = call("self_test")
        body = json.loads(r["result"]["content"][0]["text"])
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["checks"]), 14)

    def test_health_keys(self):
        r = call("health")
        body = json.loads(r["result"]["content"][0]["text"])
        for key in ("n_attempts", "validity", "discrimination",
                    "contamination"):
            self.assertIn(key, body)

    def test_run_suite_stub_sealed(self):
        # P0-2: out_root must satisfy MCP confinement — build it under
        # the resolved tempdir, never a hardcoded /tmp path (a symlink
        # on some platforms).
        out = os.path.join(tempfile.gettempdir(), "emox_mcp_test")
        r = call("run_suite", {"suite": "dynamic-code", "backend": "stub",
                               "families": ["DC1"], "out_root": out})
        try:
            self.assertIn("result", r, r.get("error"))
            summary = json.loads(r["result"]["content"][0]["text"])
            self.assertGreater(summary["n_attempts"], 0)
            rundir = summary["run_dir"]
            self.assertTrue(
                os.path.isfile(os.path.join(rundir, "seal.json")))
            man = json.load(open(os.path.join(rundir, "manifest.json")))
            self.assertEqual(man["claim_tier"], "PUBLIC-BENCHMARK")
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_hidden_gate_refuses_over_mcp(self):
        r = call("run_suite", {"suite": "code25-hidden",
                               "backend": "stub"})
        self.assertIn("error", r)
        self.assertIn("hidden-ok", r["error"]["message"])

    def test_missing_suite_is_error(self):
        r = call("run_suite", {})
        self.assertIn("error", r)

    def test_error_redacts_api_key(self):
        r = call("run_suite", {"api_key": "sk-SECRET-12345"})
        self.assertIn("error", r)
        masked = json.dumps(r["error"])
        self.assertNotIn("sk-SECRET-12345", masked)
        self.assertIn("***", masked)

    def test_compare_needs_both_runs(self):
        r = call("compare_models", {"run_a": "/tmp/x"})
        self.assertIn("error", r)

    def test_render_report_needs_run_dir(self):
        r = call("render_report", {})
        self.assertIn("error", r)


class MCPStdioTests(unittest.TestCase):
    def test_stdio_roundtrip(self):
        reqs = ('{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n'
                '{"jsonrpc":"2.0","id":2,"method":"nope"}\n')
        p = subprocess.run([sys.executable, SERVER], input=reqs,
                           capture_output=True, text=True, timeout=120)
        lines = [json.loads(l) for l in p.stdout.strip().splitlines()]
        self.assertEqual(len(lines[0]["result"]["tools"]), 6)
        self.assertEqual(lines[1]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
