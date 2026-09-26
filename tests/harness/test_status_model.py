"""Tests for Y-1 status model (stdlib unittest). SPEC B2, DEN C5-C9."""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(HERE, "..", "..", "shared"))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for _p in (SHARED, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import schemas
import manifests

try:
    from schemas import VoidRun, STATUS_CAUSES, classify_cause
    from schemas import VISIBILITY, normalize_visibility
except ImportError:  # package-layout fallback
    from shared.schemas import (VoidRun, STATUS_CAUSES, classify_cause,
                                VISIBILITY, normalize_visibility)
try:
    from manifests import verify_prompt_pack
except ImportError:
    from shared.manifests import verify_prompt_pack

EXPECTED_CAUSES = {
    "harness-bug": "VOID",
    "backend-unavailable": "VOID",
    "prompt-changed": "VOID",
    "infra-crash": "ERROR",
    "model-malformed-output": "FAIL",
    "model-timeout": "TIMEOUT",
    "missing-tool": "ERROR",
}


class TestCauseTable(unittest.TestCase):
    def test_all_seven_mappings(self):
        self.assertEqual(dict(STATUS_CAUSES), EXPECTED_CAUSES)
        for cause, status in EXPECTED_CAUSES.items():
            self.assertEqual(classify_cause(cause), status)

    def test_unknown_cause_raises(self):
        with self.assertRaises(schemas.SchemaError):
            classify_cause("no-such-cause")
        with self.assertRaises(schemas.SchemaError):
            classify_cause("")

    def test_void_run_is_exception(self):
        self.assertTrue(issubclass(VoidRun, Exception))


class TestPromptPack(unittest.TestCase):
    def test_real_pack_verifies(self):
        self.assertTrue(verify_prompt_pack("PROMPT_PACK_v2", root=ROOT))

    def test_tampered_pack_copy_raises_voidrun(self):
        tmp = tempfile.mkdtemp(prefix="emo-status-")
        try:
            os.makedirs(os.path.join(tmp, "shared"))
            os.makedirs(os.path.join(tmp, "prompts"))
            shutil.copy(os.path.join(ROOT, "prompts", "SHA256SUMS"),
                        os.path.join(tmp, "prompts", "SHA256SUMS"))
            shutil.copy(os.path.join(ROOT, "prompts", "PROMPT_PACK_v2.md"),
                        os.path.join(tmp, "prompts", "PROMPT_PACK_v2.md"))
            with open(os.path.join(tmp, "prompts", "PROMPT_PACK_v2.md"),
                      "a", encoding="utf-8") as f:
                f.write("\nTAMPERED")
            with self.assertRaises(VoidRun):
                verify_prompt_pack("PROMPT_PACK_v2", root=tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unknown_pack_raises_voidrun(self):
        with self.assertRaises(VoidRun):
            verify_prompt_pack("PROMPT_PACK_v9", root=ROOT)


class TestVisibility(unittest.TestCase):
    def test_values(self):
        self.assertEqual(tuple(VISIBILITY), ("public", "hidden", "rotating"))

    def test_default_public(self):
        self.assertEqual(normalize_visibility({}), "public")
        self.assertEqual(normalize_visibility(None), "public")

    def test_reject_unknown(self):
        with self.assertRaises(schemas.SchemaError):
            normalize_visibility({"visibility": "secret"})


if __name__ == "__main__":
    unittest.main()
