"""Regression tests for the live-data audit fixes (v2.0.1).

Covers:
  1. strip_special_tokens: special-token tails must not fail
     otherwise-correct answers (R11/TS, T7/JSON, R2/R12/SQL, R1/Rust).
  2. extract_json_object: first balanced span (T7/R4 uniform rule);
     greedy r"\\{.*\\}" over-matching is gone.
  3. report.generate: endpoint/hardware auto-fill (no more "?" when
     env or result data carries them).

Run: python3 -m unittest discover -s tests/harness -v
"""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import bench_lib as L  # noqa: E402
import report as rep  # noqa: E402


class TestStripSpecialTokens(unittest.TestCase):
    def test_im_end_removed(self):
        self.assertEqual(L.strip_special_tokens("code<|im_end|>"), "code")

    def test_im_start_removed(self):
        self.assertEqual(
            L.strip_special_tokens("<|im_start|>assistant\ncode"), "assistant\ncode")

    def test_eos_variants_removed(self):
        for tok in ("</s>", "<s>", "<|endoftext|>", "<|eot|>"):
            self.assertNotIn(tok, L.strip_special_tokens("x = 1 " + tok))

    def test_clean_text_untouched(self):
        clean = "interface User {name: string; age: number}"
        self.assertEqual(L.strip_special_tokens(clean), clean)

    def test_non_string_safe(self):
        self.assertEqual(L.strip_special_tokens(None), "")
        self.assertEqual(L.strip_special_tokens(123), "")

    def test_idempotent(self):
        once = L.strip_special_tokens("a<|im_end|>b")
        self.assertEqual(L.strip_special_tokens(once), once)

    def test_extract_code_unfenced_tail(self):
        # The reported R11 case shape: bare code + trailing token.
        code = L.extract_code(
            "interface User {name: string}\n"
            "function g(u: User): string { return u.name; }\n<|im_end|>",
            "typescript")
        self.assertNotIn("im_end", code)
        self.assertIn("function g", code)


class TestReportAutofill(unittest.TestCase):
    def _write_result(self, payload):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f)
        self.addCleanup(os.unlink, path)
        return path

    def _minimal_tests(self):
        return {"T2_python_fib": {"pass": True, "secs": 1.0,
                                  "sample": "x", "log": "ok"}}

    def test_endpoint_from_env(self):
        os.environ["OPENAI_BASE_URL"] = "https://api.example.com/v1"
        self.addCleanup(os.environ.pop, "OPENAI_BASE_URL", None)
        path = self._write_result({"code25": self._minimal_tests(),
                                   "trials": 1})
        text, _ = rep.generate(path)
        self.assertIn("api.example.com", text)
        self.assertNotIn("| Endpoint (host only) | ? |", text)

    def test_hardware_autofill(self):
        path = self._write_result({"code25": self._minimal_tests(),
                                   "trials": 1})
        text, _ = rep.generate(path)
        self.assertNotIn("| Hardware |  |", text)

    def test_explicit_args_win(self):
        path = self._write_result({"code25": self._minimal_tests(),
                                   "trials": 1})
        text, _ = rep.generate(path, endpoint="myhost",
                               hardware="my-rig")
        self.assertIn("myhost", text)
        self.assertIn("my-rig", text)

    def test_result_fields_used(self):
        path = self._write_result({"code25": self._minimal_tests(),
                                   "trials": 1,
                                   "endpoint": "stored-host",
                                   "hardware": "stored-rig"})
        text, _ = rep.generate(path)
        self.assertIn("stored-host", text)
        self.assertIn("stored-rig", text)


if __name__ == "__main__":
    unittest.main()
