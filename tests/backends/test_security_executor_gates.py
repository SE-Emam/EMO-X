"""Security executor regressions for fail-closed scope and fixture gates."""

import importlib.util
import os
import sys
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _path in (_ROOT, os.path.join(_ROOT, "shared")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

_EXEC_PATH = os.path.join(_ROOT, "suites", "security", "executor.py")
_spec = importlib.util.spec_from_file_location("security_executor_gate_tests", _EXEC_PATH)
assert _spec is not None and _spec.loader is not None
EXEC = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = EXEC
_spec.loader.exec_module(EXEC)


class SecurityScopeGateTests(unittest.TestCase):
    def test_s3_s5_scope_denial_is_void_and_never_calls_chat(self):
        for family in ("S3", "S4", "S5"):
            calls = []

            def chat(*_args, **_kwargs):
                calls.append(family)
                return "must not be called", 0.0, {}

            with self.subTest(family=family):
                with mock.patch.object(
                    EXEC,
                    "require_scope_gate",
                    side_effect=EXEC.ScopeDenied("test denial"),
                ):
                    attempt, response = EXEC.run_family(
                        family, chat, run_id="gate-test", model_id="fixture", scope=None
                    )

                self.assertEqual(calls, [])
                self.assertEqual(attempt["primary_status"], "VOID")
                self.assertEqual(attempt["primary_failure"], "SAFETY_GATE")
                self.assertFalse(attempt["eligible_for_task_score"])
                self.assertFalse(attempt["eligible_for_pass_rate"])
                self.assertEqual(response["gate"], "SAFETY_GATE")
                self.assertEqual(response["prompts"], [])
                self.assertEqual(response["replies"], [])

    def test_s3_s5_fixture_integrity_failure_is_void_before_chat(self):
        for family in ("S3", "S4", "S5"):
            calls = []

            def chat(*_args, **_kwargs):
                calls.append(family)
                return "must not be called", 0.0, {}

            with self.subTest(family=family):
                with mock.patch.object(EXEC, "require_scope_gate", return_value=True):
                    with mock.patch.object(
                        EXEC, "verify_fixture_dir", side_effect=ValueError("fixture tampered")
                    ):
                        attempt, response = EXEC.run_family(
                            family,
                            chat,
                            run_id="fixture-test",
                            model_id="fixture",
                            scope={"approved": True, "target": "synthetic:test"},
                        )

                self.assertEqual(calls, [])
                self.assertEqual(attempt["primary_status"], "VOID")
                self.assertEqual(attempt["primary_failure"], "SAFETY_GATE")
                self.assertFalse(attempt["eligible_for_task_score"])
                self.assertFalse(attempt["eligible_for_pass_rate"])
                self.assertEqual(response["gate"], "SAFETY_GATE")
                self.assertEqual(response["prompts"], [])
                self.assertEqual(response["replies"], [])


if __name__ == "__main__":
    unittest.main()
