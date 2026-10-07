"""Raw-bundle immutability seal (Y-3). SPEC sections 32-33.

Storage model: results/raw/RUN-ID/{manifest.json, events.jsonl,
responses.jsonl, environment.json} is write-once (raw -> never edited);
results/derived/RUN-ID/{...} is always regeneratable from raw plus the
seal recorded in provenance.json.

Stdlib only. English code.
"""

import datetime
import hashlib
import json
import os
import stat

#: Files covered by the seal (SPEC 33 raw layout).
BUNDLE_FILES = ("manifest.json", "events.jsonl", "responses.jsonl",
                "environment.json")

#: Name of the seal sidecar written by seal_bundle.
SEAL_NAME = "seal.json"

#: Name of the derived-bundle provenance sidecar.
PROVENANCE_NAME = "provenance.json"

#: Sealer identity recorded in seal.json.
SEALER = "emo-x seal 1.0"

#: Code version recorded in derived provenance.json.
CODE_VERSION = "1.0.0"

_READ_ONLY = 0o444


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def refuse_overwrite(out_root, run_id):
    """Return the rundir path, refusing to reuse an existing RUN_ID.

    Raises FileExistsError if out_root/run_id already exists (file or
    directory). A harness correction must mint a new RUN_ID; raw runs
    are retained, never edited.
    """
    rundir = os.path.join(out_root, run_id)
    if os.path.lexists(rundir):
        raise FileExistsError(
            "refusing to overwrite existing run %r at %s; "
            "mint a new RUN_ID, never edit raw" % (run_id, rundir))
    return rundir


def seal_bundle(rundir):
    """Hash the raw bundle files and write seal.json. Return the seal dict.

    seal.json layout: {"run_id": ..., "files": {name: sha256hex},
    "sealed_utc": ..., "sealer": ...}. All bundle files plus seal.json
    are chmodded 0o444 (read-only). Raises FileNotFoundError if a
    bundle file is missing, FileExistsError if already sealed.
    """
    if not os.path.isdir(rundir):
        raise FileNotFoundError("no such run dir: %s" % rundir)
    seal_path = os.path.join(rundir, SEAL_NAME)
    if os.path.lexists(seal_path):
        raise FileExistsError(
            "run %s is already sealed; raw is immutable" % rundir)
    files = {}
    for name in BUNDLE_FILES:
        path = os.path.join(rundir, name)
        if not os.path.isfile(path):
            raise FileNotFoundError(
                "raw bundle %s is missing %s" % (rundir, name))
        files[name] = _sha256_file(path)
    seal = {"run_id": os.path.basename(os.path.normpath(rundir)),
            "files": files,
            "sealed_utc": _utcnow(),
            "sealer": SEALER}
    _atomic_write_json(seal_path, seal)
    for name in list(BUNDLE_FILES) + [SEAL_NAME]:
        os.chmod(os.path.join(rundir, name), _READ_ONLY)
    return seal


def verify_bundle_seal(rundir):
    """Recompute raw-bundle hashes against seal.json.

    Returns (True, "ok") when every sealed file matches, else
    (False, reason). A missing seal.json yields (False, "unsealed").
    NOTE: the tuple itself is always truthy; callers must unpack and
    test the ok flag, not the tuple.
    """
    seal_path = os.path.join(rundir, SEAL_NAME)
    if not os.path.isfile(seal_path):
        return False, "unsealed"
    try:
        with open(seal_path, encoding="utf-8") as f:
            seal = json.load(f)
    except (OSError, ValueError) as exc:
        return False, "corrupt %s: %s" % (SEAL_NAME, exc)
    if not isinstance(seal, dict) or not isinstance(
            seal.get("files"), dict):
        return False, "malformed %s: 'files' mapping missing" % SEAL_NAME
    for name in BUNDLE_FILES:
        want = seal["files"].get(name)
        if not isinstance(want, str) or len(want) != 64:
            return False, "malformed seal: no sha256 for %s" % name
        path = os.path.join(rundir, name)
        if not os.path.isfile(path):
            return False, "missing bundle file: %s" % name
        got = _sha256_file(path)
        if got != want:
            return False, "tampered %s: hash mismatch" % name
    return True, "ok"


def require_seal(rundir):
    """Fail-closed gate: refuse to render/compare an unsealed bundle (P0-6).

    Returns the rundir unchanged when verify_bundle_seal passes, else
    raises ValueError naming the reason. Callers must never emit stats,
    tables, or comparisons from a bundle that fails this gate: any
    number without a sealed results/raw/RUN-ID/ bundle is inadmissible.
    """
    ok, reason = verify_bundle_seal(rundir)
    if not ok:
        raise ValueError("refusing unsealed bundle %r: %s" % (rundir, reason))
    return rundir


def _check_seal_struct(seal):
    """Return an error string if seal is not verifiable, else None."""
    if not isinstance(seal, dict):
        return "source seal is not a dict"
    files = seal.get("files")
    if not isinstance(files, dict) or not files:
        return "source seal has no 'files' mapping"
    for name in BUNDLE_FILES:
        hexval = files.get(name)
        if not isinstance(hexval, str) or len(hexval) != 64:
            return "source seal lacks a valid sha256 for %s" % name
        try:
            int(hexval, 16)
        except ValueError:
            return "source seal has non-hex sha256 for %s" % name
    for key in ("sealed_utc", "sealer"):
        if not isinstance(seal.get(key), str) or not seal[key]:
            return "source seal lacks %r" % key
    return None


def write_derived_bundle(derived_root, run_id, seal, payloads,
                         raw_rundir=None):
    """Write derived/RUN-ID/ payloads plus provenance.json. Return dir.

    payloads maps a base name to a JSON-serializable object, e.g.
    {"scores": {...}, "report": {...}} -> scores.json, report.json.
    provenance.json records {source_run_id, source_seal, derived_utc,
    code_version}, proving reproducibility from the sealed raw bundle.

    Refuses (FileExistsError) if derived_root/run_id already exists.
    Refuses (ValueError) if the source seal is structurally
    unverifiable, or -- when raw_rundir is given -- if the raw bundle
    fails verify_bundle_seal or its on-disk seal differs from `seal`.
    """
    bad = _check_seal_struct(seal)
    if bad is not None:
        raise ValueError("unverifiable source seal: %s" % bad)
    if raw_rundir is not None:
        ok, reason = verify_bundle_seal(raw_rundir)
        if not ok:
            raise ValueError(
                "unverifiable source seal: raw bundle %s: %s"
                % (raw_rundir, reason))
        with open(os.path.join(raw_rundir, SEAL_NAME),
                   encoding="utf-8") as f:
            on_disk = json.load(f)
        if on_disk.get("files") != seal.get("files"):
            raise ValueError(
                "unverifiable source seal: passed seal differs from "
                "raw bundle seal")
    rundir = os.path.join(derived_root, run_id)
    if os.path.lexists(rundir):
        raise FileExistsError(
            "refusing to overwrite existing derived run %r at %s"
            % (run_id, rundir))
    if not isinstance(payloads, dict) or not payloads:
        raise ValueError("payloads must be a non-empty dict")
    os.makedirs(rundir, exist_ok=False)
    for base, obj in payloads.items():
        fname = base if base.endswith(".json") else base + ".json"
        if os.path.basename(fname) != fname:
            raise ValueError("bad payload name: %r" % base)
        _atomic_write_json(os.path.join(rundir, fname), obj)
    provenance = {"source_run_id": run_id,
                  "source_seal": seal,
                  "derived_utc": _utcnow(),
                  "code_version": CODE_VERSION}
    _atomic_write_json(os.path.join(rundir, PROVENANCE_NAME), provenance)
    return rundir
