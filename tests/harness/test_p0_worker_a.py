"""Worker A P0 hardening tests (stdlib unittest only).

Covers: make_run_id entropy, MCP redaction, atomic tool_edit, _post_json
errors, base-URL SSRF guard, _safe trailing slash, atomic write_raw_bundle.
"""

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SHARED = os.path.join(ROOT, "shared")
for _p in (ROOT, SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import agent_tools  # noqa: E402
import backends  # noqa: E402
import runner  # noqa: E402


def _load_mcp_server():
    path = os.path.join(ROOT, "mcp-server", "server.py")
    spec = importlib.util.spec_from_file_location("emox_mcp_server_p0",
                                                  path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules["emox_mcp_server_p0"] = mod
    spec.loader.exec_module(mod)
    return mod


class MakeRunIdTests(unittest.TestCase):
    def test_format_has_micro_stamp_entropy_pid(self):
        rid = runner.make_run_id("RUN-t")
        self.assertTrue(rid.startswith("RUN-t-"), rid)
        self.assertIn("-p%d" % os.getpid(), rid)
        m = re.search(r"T\d{6}\.\d{6}Z", rid)
        self.assertIsNotNone(m, rid)
        digest = rid.split("-")[-2] if "-p" in rid else rid.rsplit("-", 1)[-1]
        # digest is the 10-hex field before the -p<PID> suffix
        core = rid[:rid.rfind("-p")]
        self.assertEqual(len(core.rsplit("-", 1)[-1]), 10)
        int(core.rsplit("-", 1)[-1], 16)

    def test_10k_ids_unique(self):
        seen = set()
        for _ in range(10000):
            seen.add(runner.make_run_id("RUN-c"))
        self.assertEqual(len(seen), 10000)


class RedactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _load_mcp_server()

    def test_sensitive_names_redacted(self):
        for name in ("api_key", "API_KEY", "apiKey", "secret",
                     "SECRET_TOKEN", "token", "password", "passwd",
                     "credentials", "cred", "Authorization",
                     "authorization-header"):
            self.assertTrue(self.srv._is_sensitive_key(name), name)

    def test_case_insensitive(self):
        self.assertTrue(self.srv._is_sensitive_key("Api_KeY"))
        self.assertTrue(self.srv._is_sensitive_key("SeCrEt"))

    def test_no_false_positives_monkey_donkey(self):
        for name in ("monkey", "donkey", "MONKEY", "Donkey",
                     "model", "suite", "families"):
            self.assertFalse(self.srv._is_sensitive_key(name), name)

    def test_redact_args_masks_values(self):
        out = self.srv._redact_args({"api_key": "sk-live-123",
                                     "model": "m", "monkey": "x"})
        self.assertEqual(out["api_key"], "***")
        self.assertEqual(out["model"], "m")
        self.assertEqual(out["monkey"], "x")

    def test_redact_args_non_dict_passthrough(self):
        self.assertEqual(self.srv._redact_args(["a"]), ["a"])


class ToolEditTests(unittest.TestCase):
    def _ctx(self, root):
        return agent_tools.Ctx(root)

    def test_atomic_edit_keeps_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "f.txt")
            with open(target, "w") as f:
                f.write("hello old world")
            ok, _ = agent_tools.tool_edit("f.txt", "old", "new",
                                          self._ctx(tmp))
            self.assertTrue(ok)
            with open(target) as f:
                self.assertEqual(f.read(), "hello new world")

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = os.path.join(tmp, "real.txt")
            with open(real, "w") as f:
                f.write("old content")
            link = os.path.join(tmp, "link.txt")
            os.symlink(real, link)
            ok, msg = agent_tools.tool_edit("link.txt", "old", "new",
                                            self._ctx(tmp))
            self.assertFalse(ok)
            self.assertIn("symlink", msg.lower())
            with open(real) as f:
                self.assertEqual(f.read(), "old content")

    def test_missing_old_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "f.txt")
            with open(target, "w") as f:
                f.write("abc")
            ok, msg = agent_tools.tool_edit("f.txt", "zzz", "new",
                                            self._ctx(tmp))
            self.assertFalse(ok)
            self.assertIn("not found", msg)


class SafeTrailingSlashTests(unittest.TestCase):
    def test_root_trailing_slash_still_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tmp + os.sep
            ctx = agent_tools.Ctx(root)
            full = agent_tools._safe("sub/file.txt", ctx)
            self.assertTrue(full.startswith(tmp.rstrip(os.sep)))
            self.assertEqual(
                agent_tools._safe(".", ctx),
                os.path.normpath(tmp))

    def test_root_trailing_slash_escape_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = agent_tools.Ctx(tmp + os.sep)
            with self.assertRaises(ValueError):
                agent_tools._safe("../../etc/passwd", ctx)


class PostJsonTests(unittest.TestCase):
    def test_http_error_raised_without_body(self):
        import io
        import urllib.error
        from unittest import mock
        fp = io.BytesIO(b"secret-body-marker-sensitive-payload")
        err = urllib.error.HTTPError(
            "http://example.com/x", 500, "Internal", {}, fp)  # type: ignore[arg-type]
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(RuntimeError) as ctx:
                backends._post_json("http://example.com/x", {"a": 1})
        msg = str(ctx.exception)
        self.assertIn("500", msg)
        self.assertIn("example.com", msg)
        self.assertNotIn("secret-body-marker", msg)

    def test_url_error_wrapped_with_host(self):
        import urllib.error
        from unittest import mock
        err = urllib.error.URLError("boom")
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(RuntimeError) as ctx:
                backends._post_json("http://example.com/y", {})
        self.assertIn("example.com", str(ctx.exception))

    def test_redact_host_strips_userinfo(self):
        host = backends._redact_host("http://user:pass@example.com:8080/v1")
        self.assertNotIn("pass", host)
        self.assertNotIn("user", host)
        self.assertIn("example.com", host)


class ValidateBaseUrlTests(unittest.TestCase):
    BLOCKED = ("http://169.254.169.254/v1",
               "http://metadata.google.internal/v1",
               "http://localhost:11434/v1",
               "http://127.0.0.1:11434/v1",
               "http://[::1]:11434/v1",
               "http://0.0.0.0:11434/v1")

    def setUp(self):
        self._prev = os.environ.get("EMOX_ALLOW_LOCAL")
        os.environ.pop("EMOX_ALLOW_LOCAL", None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("EMOX_ALLOW_LOCAL", None)
        else:
            os.environ["EMOX_ALLOW_LOCAL"] = self._prev

    def test_blocked_hosts_denied(self):
        for url in self.BLOCKED:
            with self.assertRaises(ValueError, msg=url):
                backends._validate_base_url(url)

    def test_public_host_allowed(self):
        out = backends._validate_base_url("https://api.example.com/v1")
        self.assertEqual(out, "https://api.example.com/v1")

    def test_allow_local_env_permits(self):
        os.environ["EMOX_ALLOW_LOCAL"] = "1"
        for url in self.BLOCKED:
            self.assertEqual(backends._validate_base_url(url), url)

    def test_resolve_config_enforces_guard(self):
        with self.assertRaises(ValueError):
            backends.resolve_config("openai-generic",
                                    "http://localhost:11434/v1", "m")
        os.environ["EMOX_ALLOW_LOCAL"] = "1"
        name, base, mod, _ = backends.resolve_config(
            "openai-generic", "http://localhost:11434/v1", "m")
        self.assertEqual(name, "openai-generic")
        self.assertIn("localhost", base)


class WriteRawBundleTests(unittest.TestCase):
    def _manifest(self, run_id):
        return runner.build_manifest("code25", "a" * 64, "b" * 64,
                                     "stub-model", "stub", 0, 1, run_id)

    def test_roundtrip_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "raw")
            os.makedirs(out)
            run_id = runner.make_run_id("RUN-w")
            rundir = runner.write_raw_bundle(out, self._manifest(run_id),
                                             [], [], {})
            self.assertTrue(os.path.isdir(rundir))
            for name in ("manifest.json", "events.jsonl",
                         "responses.jsonl", "environment.json",
                         "seal.json"):
                self.assertTrue(os.path.isfile(
                    os.path.join(rundir, name)), name)

    def test_crash_mid_write_leaves_no_partial_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "raw")
            os.makedirs(out)
            run_id = "RUN-crash-1"
            # Unserializable response forces json.dump to fail mid-write
            # (lengths match so the mismatch guard does not fire first).
            bad = runner._void_attempt(
                "RUN-crash-1", "m", "T", "T-1", "canonical", 1,
                "harness-bug", "x")
            with self.assertRaises(TypeError):
                runner.write_raw_bundle(out, self._manifest(run_id),
                                        [bad], [object()], {})
            self.assertFalse(os.path.lexists(os.path.join(out, run_id)),
                             "partial run dir left behind after failure")
            leftovers = [d for d in os.listdir(out)]
            self.assertEqual(leftovers, [], leftovers)

    def test_length_mismatch_fails_closed(self):
        # Attempts/responses must pair 1:1 (roadmap Phase 3: the
        # streaming writer rejects mismatched lengths loudly instead
        # of silently truncating via zip).
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "raw")
            os.makedirs(out)
            with self.assertRaises(ValueError):
                runner.write_raw_bundle(
                    out, self._manifest("RUN-mm-1"),
                    [runner._void_attempt(
                        "RUN-mm-1", "m", "T", "T-1", "canonical", 1,
                        "harness-bug", "x")], [])
            leftovers = [d for d in os.listdir(out)]
            self.assertEqual(leftovers, [], leftovers)

    def test_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "raw")
            os.makedirs(out)
            run_id = "RUN-dup-1"
            runner.write_raw_bundle(out, self._manifest(run_id), [], [],
                                    {})
            with self.assertRaises(FileExistsError):
                runner.write_raw_bundle(out, self._manifest(run_id), [],
                                        [], {})


if __name__ == "__main__":
    unittest.main()
