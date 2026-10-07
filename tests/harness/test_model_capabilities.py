"""Tests for model capability gating (modalities).

An embedding-only (or otherwise incapable) model must be REFUSED
before the first model call — scored zeros from it measure nothing
and are inadmissible, never published as 0%.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(os.path.dirname(HERE), "..", "shared")
SHARED = os.path.normpath(SHARED)
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import runner  # noqa: E402
import schemas  # noqa: E402
from safety import (
    ModelCapabilityDenied,
    parse_model_modalities,
    require_model_modality,
    stages_for_type,
    MODEL_TYPES,
)  # noqa: E402


def _stub_chat(messages, **kw):
    raise AssertionError("model must never be called after refusal")


class ParseTests(unittest.TestCase):
    def test_default_text_only(self):
        self.assertEqual(parse_model_modalities(None), frozenset(("text",)))
        self.assertEqual(parse_model_modalities(""), frozenset(("text",)))

    def test_multi(self):
        self.assertEqual(parse_model_modalities("text,vision"), frozenset(("text", "vision")))
        self.assertEqual(parse_model_modalities(["embeddings"]), frozenset(("embeddings",)))

    def test_unknown_rejected(self):
        with self.assertRaises(ValueError):
            parse_model_modalities("text,telepathy")


class GateTests(unittest.TestCase):
    def test_embedding_model_refused_on_code25(self):
        with self.assertRaises(ModelCapabilityDenied):
            require_model_modality("code25", "text", frozenset(("embeddings",)))

    def test_text_model_passes_code25(self):
        self.assertTrue(require_model_modality("code25", "text", frozenset(("text",))))

    def test_text_only_refused_on_vision(self):
        with self.assertRaises(ModelCapabilityDenied):
            require_model_modality("vision", "vision", frozenset(("text",)))

    def test_multimodal_passes_vision(self):
        self.assertTrue(require_model_modality("vision", "vision", frozenset(("text", "vision"))))


class RunnerGateTests(unittest.TestCase):
    def test_run_suite_refuses_without_calling_model(self):
        with self.assertRaises(ModelCapabilityDenied):
            runner.run_suite(
                "dynamic-code",
                _stub_chat,
                "emb-1",
                "stub",
                0,
                1,
                1,
                0.0,
                "/tmp/emox_modcap",
                families=["DC1"],
                model_modalities="embeddings",
            )

    def test_run_suite_records_modalities(self):
        import shutil

        out = "/tmp/emox_modcap_ok"
        shutil.rmtree(out, ignore_errors=True)
        rundir, _ = runner.run_suite(
            "dynamic-code",
            runner.stub_chat_factory("t"),
            "m",
            "stub",
            0,
            1,
            1,
            0.0,
            out,
            families=["DC1"],
            model_modalities="text,vision",
        )
        import json

        manifest = json.load(open(os.path.join(rundir, "manifest.json")))
        self.assertEqual(manifest["model_modalities"], ["text", "vision"])
        shutil.rmtree(out, ignore_errors=True)

    def test_manifest_rejects_bad_modalities(self):
        bad = {
            "run_id": "r",
            "suite": "s",
            "prompt_pack": "v",
            "prompt_sha256": "a" * 64,
            "harness_sha256": "b" * 64,
            "model": "m",
            "backend": "b",
            "seed": 0,
            "trials": 1,
            "model_modalities": [],
        }
        with self.assertRaises(ValueError):
            schemas.validate_run_manifest(bad)


class ModelTypeTests(unittest.TestCase):
    def test_registry_covers_generative_family(self):
        for t in ("llm", "chat", "code", "reasoning", "math", "agentic"):
            self.assertIn("text", MODEL_TYPES[t]["modalities"], t)

    def test_stages_text_types(self):
        self.assertEqual(
            stages_for_type("code"), ["smoke", "code", "agent", "assurance", "horizon"]
        )

    def test_multimodal_adds_eyes(self):
        self.assertIn("eyes", stages_for_type("multimodal"))

    def test_embedding_refused_with_pointer(self):
        with self.assertRaises(ModelCapabilityDenied) as ctx:
            stages_for_type("embedding")
        self.assertIn("MTEB", str(ctx.exception))

    def test_jev_refused_with_pointer(self):
        with self.assertRaises(ModelCapabilityDenied) as ctx:
            stages_for_type("jev-decision")
        self.assertIn("TypeSafe", str(ctx.exception))

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            stages_for_type("telepathy")

    def test_run_suite_rejects_bad_type(self):
        with self.assertRaises(ValueError):
            runner.run_suite(
                "dynamic-code",
                _stub_chat,
                "m",
                "stub",
                0,
                1,
                1,
                0.0,
                "/tmp/emox_modcap",
                families=["DC1"],
                model_type="telepathy",
            )

    def test_run_suite_rejects_out_of_scope_type(self):
        with self.assertRaises(ModelCapabilityDenied):
            runner.run_suite(
                "dynamic-code",
                _stub_chat,
                "m",
                "stub",
                0,
                1,
                1,
                0.0,
                "/tmp/emox_modcap",
                families=["DC1"],
                model_type="embedding",
            )

    def test_manifest_records_type(self):
        import json
        import shutil

        out = "/tmp/emox_modcap_type"
        shutil.rmtree(out, ignore_errors=True)
        rundir, _ = runner.run_suite(
            "dynamic-code",
            runner.stub_chat_factory("t"),
            "m",
            "stub",
            0,
            1,
            1,
            0.0,
            out,
            families=["DC1"],
            model_type="code",
        )
        manifest = json.load(open(os.path.join(rundir, "manifest.json")))
        self.assertEqual(manifest["model_type"], "code")
        self.assertEqual(manifest["model_modalities"], ["text"])
        shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
