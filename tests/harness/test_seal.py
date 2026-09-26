"""Tests for shared/seal.py (stdlib unittest). Y-3 acceptance."""

import json
import os
import stat
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.normpath(os.path.join(os.path.dirname(HERE), "..",
                                       "shared"))
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import seal

RAW_FILES = {"manifest.json": {"run_id": "RUN-1"},
             "events.jsonl": '{"a": 1}\n',
             "responses.jsonl": '{"r": 1}\n',
             "environment.json": {"env": "test"}}


def make_raw(root, run_id="RUN-1"):
    rundir = os.path.join(root, run_id)
    os.makedirs(rundir)
    for name, obj in RAW_FILES.items():
        path = os.path.join(rundir, name)
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(obj, str):
                f.write(obj)
            else:
                json.dump(obj, f)
    return rundir


def make_writable(path):
    os.chmod(path, 0o644)


class TestSealVerify(unittest.TestCase):
    def test_seal_then_verify_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = make_raw(tmp)
            s = seal.seal_bundle(rundir)
            self.assertEqual(set(s["files"]), set(seal.BUNDLE_FILES))
            self.assertIn("sealed_utc", s)
            self.assertIn("sealer", s)
            self.assertTrue(os.path.isfile(
                os.path.join(rundir, "seal.json")))
            ok, reason = seal.verify_bundle_seal(rundir)
            self.assertEqual((ok, reason), (True, "ok"))

    def test_seal_makes_files_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = make_raw(tmp)
            seal.seal_bundle(rundir)
            for name in list(seal.BUNDLE_FILES) + ["seal.json"]:
                mode = stat.S_IMODE(os.stat(
                    os.path.join(rundir, name)).st_mode)
                self.assertEqual(mode, 0o444, name)

    def test_unsealed_dir_reports_unsealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = make_raw(tmp)
            self.assertEqual(seal.verify_bundle_seal(rundir),
                             (False, "unsealed"))

    def test_tamper_one_byte_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = make_raw(tmp)
            seal.seal_bundle(rundir)
            target = os.path.join(rundir, "events.jsonl")
            make_writable(target)
            with open(target, "ab") as f:
                f.write(b" ")
            ok, reason = seal.verify_bundle_seal(rundir)
            self.assertFalse(ok)
            self.assertIn("events.jsonl", reason)

    def test_tamper_each_file_detected(self):
        for name in seal.BUNDLE_FILES:
            with tempfile.TemporaryDirectory() as tmp:
                rundir = make_raw(tmp)
                seal.seal_bundle(rundir)
                target = os.path.join(rundir, name)
                make_writable(target)
                with open(target, "ab") as f:
                    f.write(b"X")
                ok, reason = seal.verify_bundle_seal(rundir)
                self.assertFalse(ok, name)
                self.assertIn(name, reason)

    def test_reseal_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = make_raw(tmp)
            seal.seal_bundle(rundir)
            with self.assertRaises(FileExistsError):
                seal.seal_bundle(rundir)

    def test_seal_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = make_raw(tmp)
            os.remove(os.path.join(rundir, "responses.jsonl"))
            with self.assertRaises(FileNotFoundError):
                seal.seal_bundle(rundir)


class TestRefuseOverwrite(unittest.TestCase):
    def test_existing_dir_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_raw(tmp, "RUN-9")
            with self.assertRaises(FileExistsError):
                seal.refuse_overwrite(tmp, "RUN-9")

    def test_fresh_id_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rundir = seal.refuse_overwrite(tmp, "RUN-NEW")
            self.assertEqual(rundir, os.path.join(tmp, "RUN-NEW"))


class TestDerivedBundle(unittest.TestCase):
    def _sealed(self, tmp, run_id="RUN-1"):
        rundir = make_raw(tmp, run_id)
        s = seal.seal_bundle(rundir)
        return rundir, s

    def test_derived_provenance_links_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            rawdir, s = self._sealed(tmp)
            payloads = {"scores": {"pass": 1}, "report": {"n": 1}}
            ddir = seal.write_derived_bundle(
                os.path.join(tmp, "derived"), "RUN-1", s, payloads,
                raw_rundir=rawdir)
            for fname in ("scores.json", "report.json",
                          "provenance.json"):
                self.assertTrue(os.path.isfile(
                    os.path.join(ddir, fname)), fname)
            with open(os.path.join(ddir, "provenance.json"),
                       encoding="utf-8") as f:
                prov = json.load(f)
            self.assertEqual(prov["source_run_id"], "RUN-1")
            self.assertEqual(prov["source_seal"], s)
            self.assertIn("derived_utc", prov)
            self.assertIn("code_version", prov)

    def test_derived_without_raw_still_needs_structural_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, s = self._sealed(tmp)
            ddir = seal.write_derived_bundle(
                os.path.join(tmp, "derived"), "RUN-1", s,
                {"scores": {}})
            self.assertTrue(os.path.isfile(
                os.path.join(ddir, "provenance.json")))

    def test_derived_refuses_bad_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                seal.write_derived_bundle(
                    os.path.join(tmp, "derived"), "RUN-1", {}, {"a": {}})
            with self.assertRaises(ValueError):
                seal.write_derived_bundle(
                    os.path.join(tmp, "derived"), "RUN-1", None, {"a": {}})

    def test_derived_refuses_tampered_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            rawdir, s = self._sealed(tmp)
            target = os.path.join(rawdir, "responses.jsonl")
            make_writable(target)
            with open(target, "ab") as f:
                f.write(b"tamper")
            with self.assertRaises(ValueError):
                seal.write_derived_bundle(
                    os.path.join(tmp, "derived"), "RUN-1", s,
                    {"scores": {}}, raw_rundir=rawdir)

    def test_derived_refuses_mismatched_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            rawdir, s = self._sealed(tmp)
            other = dict(s)
            other["files"] = dict(s["files"])
            other["files"]["manifest.json"] = "0" * 64
            with self.assertRaises(ValueError):
                seal.write_derived_bundle(
                    os.path.join(tmp, "derived"), "RUN-1", other,
                    {"scores": {}}, raw_rundir=rawdir)

    def test_derived_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            rawdir, s = self._sealed(tmp)
            root = os.path.join(tmp, "derived")
            seal.write_derived_bundle(root, "RUN-1", s, {"scores": {}},
                                      raw_rundir=rawdir)
            with self.assertRaises(FileExistsError):
                seal.write_derived_bundle(root, "RUN-1", s,
                                          {"scores": {}},
                                          raw_rundir=rawdir)


if __name__ == "__main__":
    unittest.main()
