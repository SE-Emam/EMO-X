"""Tests for recovery_precision (SPEC 14): diagnosis vs thrashing luck."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scoring import recovery_precision  # noqa: E402


def act(tool, args, prev_error="", **flags):
    d = {"tool": tool, "args": args, "prev_error": prev_error,
         "is_repeat_identical": False, "is_verification_run": False}
    d.update(flags)
    return d


class RecoveryPrecisionTests(unittest.TestCase):
    def test_lexical_link_positive(self):
        a = act("read", {"path": "shop/taxes.py"},
                "ERROR: no such file: shop/taxes.py")
        self.assertEqual(recovery_precision([a]), 1.0)

    def test_lexical_link_negative(self):
        a = act("ls", {"path": "."}, "ERROR: assertion failed in taxes")
        self.assertEqual(recovery_precision([a]), 0.0)

    def test_blind_identical_repeat_excluded(self):
        a = act("run", {"cmd": "pytest -x"}, "timeout",
                retry_of_failed=True, modified_args=0,
                is_repeat_identical=True)
        self.assertEqual(recovery_precision([a]), 0.0)

    def test_targeted_retry_counts(self):
        a = act("run", {"cmd": "pytest shop/tests/ -x"}, "timeout",
                retry_of_failed=True, modified_args=1)
        self.assertEqual(recovery_precision([a]), 1.0)

    def test_verification_counts(self):
        a = act("run", {"cmd": "pytest"}, "fixed",
                is_verification_run=True)
        self.assertEqual(recovery_precision([a]), 1.0)

    def test_empty_window_is_na(self):
        self.assertIsNone(recovery_precision([]))

    def test_thrashing_discriminator(self):
        # 20 random actions, 1 linked: high rate possible, precision 0.05.
        acts = [act("ls", {"path": "."}, "unrelated noise") for _ in range(19)]
        acts.append(act("read", {"path": "shop/taxes.py"},
                        "ERROR: no such file: shop/taxes.py"))
        self.assertAlmostEqual(recovery_precision(acts), 0.05)

    def test_mixed_hand_computed(self):
        acts = [
            act("read", {"path": "shop/taxes.py"},
                "ERROR: no such file: shop/taxes.py"),
            act("run", {"cmd": "pytest"}, "fixed",
                is_verification_run=True),
            act("ls", {"path": "."}, "assertion failed"),
        ]
        self.assertAlmostEqual(recovery_precision(acts), 2 / 3)


if __name__ == "__main__":
    unittest.main()
