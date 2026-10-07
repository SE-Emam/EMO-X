"""Atomic raw-bundle writing and sealing (SPEC 33)."""

import contextlib
import datetime
import hashlib
import json
import os

try:
    from schemas import validate_attempt
except ImportError:
    from shared.schemas import validate_attempt


class BundleStream:
    """Incrementally write then atomically publish one immutable run bundle."""

    def __init__(self, out_root, run_id):
        try:
            from seal import refuse_overwrite, seal_bundle
        except ImportError:
            from shared.seal import refuse_overwrite, seal_bundle
        self._seal_bundle = seal_bundle
        self.rundir = refuse_overwrite(out_root, run_id)
        self.staging = "%s.staging-%d-%s" % (
            self.rundir,
            os.getpid(),
            hashlib.sha256(os.urandom(16)).hexdigest()[:8],
        )
        if os.path.lexists(self.staging):
            raise FileExistsError(f"staging dir already exists: {self.staging}")
        os.makedirs(self.staging, exist_ok=False)
        self._events = open(
            os.path.join(self.staging, "events.jsonl"), "w", encoding="utf-8"
        )
        self._responses = open(
            os.path.join(self.staging, "responses.jsonl"), "w", encoding="utf-8"
        )
        self._closed = False

    def append(self, attempt, response):
        """Validate and flush one attempt/response pair."""
        self._events.write(
            json.dumps(validate_attempt(attempt), ensure_ascii=False) + "\n"
        )
        self._events.flush()
        self._responses.write(json.dumps(response, ensure_ascii=False) + "\n")
        self._responses.flush()

    def close(self, manifest, environment=None):
        """Write metadata, atomically publish, and seal the bundle."""
        self._events.close()
        self._responses.close()
        with open(
            os.path.join(self.staging, "manifest.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        env = dict(environment or {})
        env.setdefault(
            "written_utc", datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        with open(
            os.path.join(self.staging, "environment.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(env, f, ensure_ascii=False, indent=1)
        try:
            os.rename(self.staging, self.rundir)
        except BaseException:
            import shutil

            try:
                if os.path.isdir(self.staging) and not os.path.lexists(self.rundir):
                    shutil.rmtree(self.staging, ignore_errors=True)
            finally:
                raise
        self._closed = True
        self._seal_bundle(self.rundir)
        return self.rundir

    def abort(self):
        """Discard an unpublished staging directory."""
        import shutil

        with contextlib.suppress(Exception):
            self._events.close()
        with contextlib.suppress(Exception):
            self._responses.close()
        if not self._closed:
            shutil.rmtree(self.staging, ignore_errors=True)


def write_raw_bundle(out_root, manifest, attempts, responses, environment=None):
    """Write a schema-checked run bundle and return its final directory."""
    stream = BundleStream(out_root, manifest["run_id"])
    try:
        n_attempts, n_responses = len(attempts), len(responses)
    except TypeError:
        n_attempts = n_responses = None
    if n_attempts is not None and n_attempts != n_responses:
        stream.abort()
        raise ValueError(
            "attempts/responses length mismatch: %d != %d" % (n_attempts, n_responses)
        )
    try:
        for attempt, response in zip(attempts, responses, strict=False):
            stream.append(attempt, response)
        return stream.close(manifest, environment)
    except BaseException:
        stream.abort()
        raise
