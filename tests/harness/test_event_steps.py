"""Tests for adapters/event_steps.py + delegation (auditor P1-17)."""

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


ES = _load("event_steps_under_test",
           os.path.join(ADAPTERS, "event_steps.py"))

SAMPLES = ['{"tool": "read", "args": {"path": "x"}, "result": "ok"}',
           'not json at all',
           '{"a": 1}',
           '{"function": "edit", "params": ["a"], "output": {"k": 1}}',
           '', '   ']


class CanonicalStepsTests(unittest.TestCase):
    def test_tool_line(self):
        out = ES.normalize_jsonl_events(SAMPLES[0])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["tool"], "read")
        self.assertEqual(out[0]["args"], {"path": "x"})
        self.assertEqual(out[0]["index"], 1)

    def test_raw_lines_kept(self):
        out = ES.normalize_jsonl_events(
            SAMPLES[1] + "\n" + SAMPLES[0])
        self.assertEqual(out[-1]["tool"], "raw_output")
        self.assertIn("not json", out[-1]["result"])

    def test_empty_input(self):
        out = ES.normalize_jsonl_events("")
        self.assertEqual(len(out), 1)
        self.assertIn("empty", out[0]["result"])

    def test_truncation(self):
        out = ES.normalize_jsonl_events('{"tool": "%s"}' % ("t" * 5000),
                                        trunc=100)
        self.assertLessEqual(len(out[0]["tool"]), 80)


class NoDriftTests(unittest.TestCase):
    def test_adapters_match_canonical(self):
        op = _load("op_norm_test",
                   os.path.join(ADAPTERS, "opencode_adapter.py"))
        pi = _load("pi_norm_test",
                   os.path.join(ADAPTERS, "pi_adapter.py"))
        for sample in SAMPLES:
            self.assertEqual(op._normalize_events(sample),
                             ES.normalize_jsonl_events(sample),
                             sample)
            self.assertEqual(pi._normalize_events(sample),
                             ES.normalize_jsonl_events(sample),
                             sample)


if __name__ == "__main__":
    unittest.main()
