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
    def test_ground_truth_matches_frozen_scene_contracts(self):
        with open(_GT_PATH, encoding="utf-8") as handle:
            gt = json.load(handle)

        expected_boxes = {
            ("ui_login.png", "login_button"): [175, 633, 425, 717],
            ("ui_login.png", "cancel_button"): [450, 633, 700, 717],
            ("ui_login.png", "help_button"): [175, 767, 300, 825],
            ("ui_login.png", "search_box"): [650, 117, 850, 167],
            ("ui_login.png", "username_field"): [175, 317, 700, 383],
            ("ui_toolbar.png", "save_button"): [75, 87, 225, 163],
            ("ui_toolbar.png", "settings_button"): [250, 87, 425, 163],
            ("ui_toolbar.png", "delete_button"): [450, 87, 612, 163],
            ("ui_toolbar.png", "toolbar_search"): [638, 87, 925, 163],
            ("ui_login_noisy.png", "login_button"): [175, 633, 425, 717],
        }
        expected_labels_colors = {
            ("ui_login.png", "login_button"): ("red LOGIN button", "red"),
            ("ui_login.png", "cancel_button"): ("green Cancel button", "green"),
            ("ui_login.png", "help_button"): ("blue Help button", "blue"),
            ("ui_toolbar.png", "save_button"): ("blue SAVE button", "blue"),
            ("ui_toolbar.png", "settings_button"): ("gray Settings button", "gray"),
            ("ui_toolbar.png", "delete_button"): ("red Delete button", "red"),
        }
        for (filename, key), expected_box in expected_boxes.items():
            with self.subTest(fixture=filename, target=key):
                self.assertEqual(gt[filename][key]["box"], expected_box)
        for (filename, key), (label, color) in expected_labels_colors.items():
            with self.subTest(fixture=filename, target=key):
                self.assertEqual(gt[filename][key]["label"], label)
                self.assertEqual(gt[filename][key]["color"], color)

        self.assertEqual(gt["grid_count.png"]["blue_circles"], 7)
        self.assertEqual(gt["grid_count.png"]["red_squares"], 4)
        self.assertEqual(gt["grid_count.png"]["total_shapes"], 11)
        self.assertEqual(gt["grid_count_perturbed.png"]["blue_circles"], 7)
        self.assertEqual(gt["grid_count_perturbed.png"]["red_squares"], 4)
        self.assertEqual(
            gt["arabic_card.png"]["lines"],
            ["تسجيل الدخول", "مرحبا بك في المتجر", "زر الدخول أحمر"],
        )
        self.assertEqual(gt["arabic_card.png"]["keywords"], ["تسجيل", "الدخول", "مرحبا", "المتجر", "زر", "أحمر"])
        self.assertEqual(
            gt["diff_pair"]["change"],
            {"object": "middle square", "type": "color", "from": "blue", "to": "red"},
        )
        self.assertEqual(
            gt["spatial.png"]["relation"], "above"
        )
        self.assertEqual(gt["chart.png"]["bars"], {"blue": 4, "red": 7, "green": 3})
        self.assertEqual(
            gt["table_orders.png"]["rows"],
            [
                {"item": "A", "qty": 2, "amount": 20},
                {"item": "B", "qty": 1, "amount": 35},
                {"item": "C", "qty": 4, "amount": 15},
            ],
        )

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
