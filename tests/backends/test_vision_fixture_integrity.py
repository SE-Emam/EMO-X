"""Integrity checks for the frozen Vision fixture pack and ground truth."""

import hashlib
import importlib.util
import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _path in (_ROOT, os.path.join(_ROOT, "shared")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

_RUNNER_PATH = os.path.join(_ROOT, "vision-bench", "run_vision.py")
_spec = importlib.util.spec_from_file_location("vision_fixture_integrity_runner", _RUNNER_PATH)
assert _spec is not None and _spec.loader is not None
VB = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = VB
_spec.loader.exec_module(VB)

_FIX_DIR = os.path.join(_ROOT, "vision-bench", "fixtures")
_GT_PATH = os.path.join(_FIX_DIR, "ground_truth.json")


class VisionFixtureIntegrityTests(unittest.TestCase):
    def test_frozen_fixture_hashes_and_ground_truth_contracts(self):
        with open(_GT_PATH, encoding="utf-8") as handle:
            gt = json.load(handle)

        fixture_hashes = gt["fixture_sha256"]
        tests = VB.build_tests(gt)
        self.assertEqual(len(tests), 12)

        referenced = set()
        for _name, images, _prompt, _target in tests:
            image_paths = images if isinstance(images, list) else [images]
            for image_path in image_paths:
                filename = os.path.basename(image_path)
                referenced.add(filename)
                self.assertIn(filename, fixture_hashes)
                self.assertTrue(os.path.isfile(image_path), image_path)

        self.assertTrue(referenced.issubset(set(fixture_hashes)))
        for filename, expected_sha in fixture_hashes.items():
            path = os.path.join(_FIX_DIR, filename)
            with self.subTest(fixture=filename):
                self.assertTrue(os.path.isfile(path), path)
                with open(path, "rb") as handle:
                    payload = handle.read()
                self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"), filename)
                self.assertEqual(hashlib.sha256(payload).hexdigest(), expected_sha)
                self.assertGreater(int.from_bytes(payload[16:20], "big"), 0)
                self.assertGreater(int.from_bytes(payload[20:24], "big"), 0)

        scale = gt["box_scale"]
        for filename in ("ui_login.png", "ui_toolbar.png", "ui_login_noisy.png"):
            button_key = "login_button" if filename != "ui_toolbar.png" else "save_button"
            box = gt[filename][button_key]["box"]
            self.assertEqual(len(box), 4)
            x1, y1, x2, y2 = box
            self.assertTrue(0 <= x1 < x2 <= scale, (filename, box))
            self.assertTrue(0 <= y1 < y2 <= scale, (filename, box))

        self.assertTrue({"middle", "square", "red"}.issubset(set(gt["diff_pair"]["keywords"])))
        self.assertEqual(
            gt["chart.png"]["bars"][gt["chart.png"]["target_color"]],
            gt["chart.png"]["target_value"],
        )
        self.assertEqual(
            gt["table_orders.png"]["row_count"],
            len(gt["table_orders.png"]["rows"]),
        )
        target_row = next(
            row
            for row in gt["table_orders.png"]["rows"]
            if row["item"] == gt["table_orders.png"]["target_item"]
        )
        self.assertEqual(target_row["amount"], gt["table_orders.png"]["target_amount"])
        self.assertTrue(gt["arabic_card.png"]["keywords"])
        self.assertIn(gt["spatial.png"]["relation"], VB.V8_RELATIONS)


if __name__ == "__main__":
    unittest.main()
