#!/usr/bin/env bash
# run_official_baseline.sh — R3 official-baseline gate runner (SPEC B59).
#
# Model-agnostic. Configuration comes from the environment only:
#   MODEL    (required) model identifier, e.g. qwen3:2b
#   BACKEND  (required) backend name, e.g. ollama | kaggle | openai-generic
#   BASE_URL (optional) endpoint URL for remote backends
#   OUT      (optional) output root, default: results
#
# Flow: self-test gate -> code25, 3 trials, frozen seed 0 -> seal verify
# -> R3 checklist. Fails closed (nonzero exit) on ANY gate miss.
#
# Usage:
#   MODEL=qwen3:2b BACKEND=ollama bash scripts/run_official_baseline.sh
#   MODEL=NAME BACKEND=kaggle BASE_URL=URL OUT=/tmp/base bash scripts/run_official_baseline.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL="${MODEL:-}"
BACKEND="${BACKEND:-}"
BASE_URL="${BASE_URL:-}"
OUT="${OUT:-results}"

fail() { echo "GATE FAIL: $1" >&2; exit 1; }
pass() { echo "GATE PASS: $1"; }

[ -n "$MODEL" ] || fail "MODEL is empty (export MODEL=<model-id>)"
[ -n "$BACKEND" ] || fail "BACKEND is empty (export BACKEND=<backend>)"
pass "env MODEL=$MODEL BACKEND=$BACKEND OUT=$OUT"

# --- Gate 0: self-test must be green before any baseline number exists. ---
python3 shared/run.py --self-test \
  || fail "self-test gate (--self-test did not PASS)"
pass "self-test"

# --- Official baseline run: code25, exactly 3 trials, frozen seed 0. ---
RUN_ARGS=(shared/run.py --suite code25 --backend "$BACKEND" --model "$MODEL"
  --trials 3 --seed 0 --out "$OUT")
if [ -n "$BASE_URL" ]; then
  RUN_ARGS+=(--base-url "$BASE_URL")
fi
python3 "${RUN_ARGS[@]}" \
  || fail "baseline run failed (suite code25, trials 3, seed 0)"
pass "baseline run finished (code25 x3, seed 0)"

# --- Locate the newest raw bundle under $OUT/raw. ---
BUNDLE="$(python3 - "$OUT" <<'EOF'
import json, os, sys
root = os.path.join(sys.argv[1], "raw")
best = None
try:
    cands = [d for d in os.listdir(root)
             if os.path.isfile(os.path.join(root, d, "manifest.json"))]
except OSError as exc:
    print("cannot list %s: %s" % (root, exc))
    raise SystemExit(1)
for d in cands:
    mp = os.path.join(root, d, "manifest.json")
    try:
        with open(mp, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError):
        continue
    key = (m.get("timestamp_utc", ""), d)
    if best is None or key > best[0]:
        best = (key, os.path.join(root, d))
if best is None:
    print("no bundle with manifest.json under %s" % root)
    raise SystemExit(1)
print(best[1])
EOF
)" || fail "no sealed bundle found under $OUT/raw"
echo "bundle: $BUNDLE"

# --- Verify seal + R3 manifest/coverage/CSVRate gates (fail-closed). ---
export R3_BUNDLE="$BUNDLE"
python3 - <<'EOF'
import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "shared"))
from seal import verify_bundle_seal

rundir = os.environ["R3_BUNDLE"]
fails = []
def check(name, ok, detail=""):
    print("%-12s %s %s" % (name, "PASS" if ok else "FAIL", detail))
    if not ok:
        fails.append(name)

try:
    with open(os.path.join(rundir, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
except (OSError, ValueError) as exc:
    print("manifest   FAIL cannot read manifest.json: %s" % exc)
    raise SystemExit(1)

required = ("benchmark_version", "suite", "prompt_pack", "prompt_sha256",
            "harness_sha256", "model", "backend", "seed", "trials")
missing = [k for k in required if k not in manifest]
check("manifest", not missing,
      "all SPEC-32 fields recorded" if not missing
      else "missing fields: %s" % ",".join(missing))
check("trials", manifest.get("trials") == 3,
      "trials=%r (want 3)" % manifest.get("trials"))
check("seed", manifest.get("seed") == 0,
      "seed=%r (want frozen 0)" % manifest.get("seed"))

ok, reason = verify_bundle_seal(rundir)
check("seal", ok, reason)

# Coverage from raw events: scored / total, fail-closed on empty/unknown.
SCORED = {"PASS", "PARTIAL", "FAIL", "TIMEOUT", "INVALID"}
try:
    n_total, n_scored = 0, 0
    with open(os.path.join(rundir, "events.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n_total += 1
            if json.loads(line).get("primary_status") in SCORED:
                n_scored += 1
    coverage = (n_scored / n_total) if n_total else None
except (OSError, ValueError) as exc:
    coverage, n_total, n_scored = None, 0, 0
    print("coverage   FAIL cannot read events.jsonl: %s" % exc)
    fails.append("coverage")
else:
    cov_txt = ("None" if coverage is None else "%.4f" % coverage)
    check("coverage", coverage is not None and coverage >= 0.95,
          "coverage=%s (%d/%d scored)" % (cov_txt, n_scored, n_total))

# CSVRate: code25 bundles carry no security cases, so look for an explicit
# derived csv_rate next to the bundle; unknown CSV fails closed (ineligible).
csv_rate = None
for cand in (os.path.join(rundir, "report.json"),
             os.path.join(rundir, "scores.json")):
    try:
        with open(cand, encoding="utf-8") as f:
            csv_rate = json.load(f).get("csv_rate", csv_rate)
    except (OSError, ValueError):
        pass
if csv_rate is None:
    check("csv_rate", False,
          "CSVRate unknown for code25 bundle "
          "(attach security bundle/report; unknown CSV is ineligible)")
else:
    check("csv_rate", csv_rate == 0, "CSVRate=%r (want 0)" % csv_rate)

if fails:
    print("R3 CHECKLIST: FAIL (%s)" % ", ".join(fails))
    raise SystemExit(1)
print("R3 CHECKLIST: PASS (trials=3, seed=0, manifest, seal, "
      "coverage>=0.95, CSVRate=0)")
EOF
# shellcheck disable=SC2181
[ $? -eq 0 ] || fail "R3 checklist gate"
pass "R3 official-baseline checklist"
echo "OFFICIAL BASELINE OK: $BUNDLE"
