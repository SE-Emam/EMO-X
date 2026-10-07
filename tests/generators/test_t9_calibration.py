"""Regression checks for the frozen T9 Spanish closure calibration set."""

import importlib.util
import json
import os
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SUITE = os.path.join(ROOT, "suites", "code-bench-25")


def _load_executor():
    path = os.path.join(SUITE, "executor.py")
    spec = importlib.util.spec_from_file_location("code25_t9_calibration_executor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load code25 executor from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class T9CalibrationTests(unittest.TestCase):
    def test_calibration_labels_match_t9_oracle(self):
        path = os.path.join(SUITE, "t9_calibration.json")
        with open(path, encoding="utf-8") as calibration_file:
            calibration = json.load(calibration_file)

        items = calibration["items"]
        self.assertEqual(len(items), 16)
        self.assertEqual(sum(item["expected"] is True for item in items), 8)
        self.assertEqual(sum(item["expected"] is False for item in items), 8)

        executor = _load_executor()
        for index, item in enumerate(items):
            with self.subTest(index=index, expected=item["expected"]):
                passed, log = executor.check_family("T9", item["reply"])
                self.assertEqual(passed, item["expected"], log)


if __name__ == "__main__":
    unittest.main()
