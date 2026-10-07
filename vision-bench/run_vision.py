"""vision-bench runner (PROMPT_PACK vision-v1).

Sends OpenAI-style image_url messages through shared/backends.py chat().
Stdlib + urllib only. No network except model chat calls (and the
capability probe, which is itself a model-endpoint call).

Gating (PLAN 3.4: blocked until a VLM endpoint exists):
  1. Best-effort GET {base}/models scan for vision tokens.
  2. Mandatory tiny-image probe call before the suite.
  Either showing lack of image support -> graceful SKIP:
  prints SKIP reason, writes a {status: skipped} JSON to --out, exit 0.
  Override with --force (records forced: true; a failed image call then
  marks each test error instead of pass).

  python vision-bench/run_vision.py --backend openai-generic --out results/
  python vision-bench/run_vision.py --only V1,V3 --trials 3 --out results/
  python vision-bench/run_vision.py --list
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(os.path.dirname(HERE), "shared")
for p in (HERE, SHARED):
    if p not in sys.path:
        sys.path.insert(0, p)

from backends import make_chat  # noqa: E402  (local import keeps error clean)

PROMPT_PACK = "vision-v1"
TEMP = 0.2
MAX_TOKENS = 512
IOU_PASS = 0.5

FIX_DIR = os.path.join(HERE, "fixtures")
GT_PATH = os.path.join(FIX_DIR, "ground_truth.json")

# --- frozen prompts (byte-frozen under PROMPT_PACK vision-v1) ---
P_GROUND = (
    "Locate the {label} in this UI screenshot. "
    "Reply with ONLY a JSON object, no markdown, no explanation: "
    '\'{{"x": <left>, "y": <top>, "w": <width>, "h": <height>}}\' '
    "with coordinates normalized to 0-1000 (origin top-left)."
)
P_ARABIC = (
    "Read ALL Arabic text visible in this image. "
    "Reply with ONLY the transcribed text lines, no explanation."
)
P_COUNT = (
    "How many {what} are visible in this image? Reply with ONLY a single integer, no explanation."
)

# tokens suggesting an endpoint/model accepts images (best-effort only;
# the probe image call below is the binding check, not this list)
VISION_TOKENS = (
    "vision",
    "vl",
    "image",
    "multimodal",
    "llava",
    "qwen-vl",
    "qwen2-vl",
    "qwen2.5-vl",
    "gpt-4o",
    "gpt-4-vision",
    "gemini",
    "claude-3",
    "pixtral",
    "llama-3.2-vision",
    "minicpm-v",
    " CogVLM".lower(),
    "internvl",
    "ocr",
)

# error text proving the endpoint rejected the IMAGE (not a generic failure)
NO_IMAGE_RE = re.compile(
    r"image|vision|multimodal|unsupported.*content|content.*type|"
    r"invalid.*media|media.*type|base64|data url|content part",
    re.I,
)


def load_ground_truth():
    with open(GT_PATH) as f:
        return json.load(f)


def img_data_url(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return "data:image/png;base64," + b64


def vision_messages(prompt, image_path):
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": img_data_url(image_path)}},
            ],
        }
    ]


# ---------------- capability gating ----------------


def models_hint_supports_vision(base_url, timeout=20):
    """GET {base}/models; True/False/None(unknown). Never raises.

    Auditor MEDIUM: validate the URL first (fail-closed on metadata /
    loopback unless EMOX_ALLOW_LOCAL=1) — this helper reaches the
    network with a caller-supplied base.
    """
    try:
        from backends import _validate_base_url  # noqa: E402

        _validate_base_url(base_url)
    except Exception:
        return None
    url = base_url.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.load(r)
        blob = json.dumps(body).lower()
        if any(t in blob for t in VISION_TOKENS):
            return True
        ids = [d.get("id", "") for d in body.get("data", [])]
        if ids:  # models listed, none looks visual -> weak negative
            return False
        return None
    except Exception:
        return None


def probe_image_call(chat, timeout_note=""):
    """Send a 1x1 probe image. Returns (ok, detail). Never raises."""
    _ = timeout_note
    try:
        import struct
        import zlib

        # minimal 1x1 red PNG, stdlib-built (no PIL at runtime)
        def chunk(t, d):
            c = struct.pack(">I", len(d)) + t + d
            return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        raw = b"\x00\xff\x00\x00"
        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )
        tiny = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Reply with ONLY the word OK."},
                    {"type": "image_url", "image_url": {"url": tiny}},
                ],
            }
        ]
        text, _, _ = chat(msgs, temp=0.0, max_tokens=16)
        return True, (text or "")[:100]
    except Exception as e:
        msg = str(e)[:300]
        if NO_IMAGE_RE.search(msg):
            return False, "endpoint rejects image content: " + msg
        return False, "probe failed (ambiguous, treating as unsupported): " + msg


def gate_check(chat, base_url, force):
    """Returns None if the suite may run, else a skip-reason string."""
    if force:
        return None
    hint = models_hint_supports_vision(base_url)
    ok, detail = probe_image_call(chat)
    if ok:
        return None
    if hint is False:
        return "no vision model advertised at /models AND probe image call failed (%s)" % detail
    return "probe image call failed (%s)" % detail


# ---------------- judges (pure functions, offline-testable) ----------------

BOX_RE = re.compile(r"\{[^{}]*\"x(?:_min)?\"[^{}]*\}")


def parse_box(text):
    """Extract {x,y,w,h} (or x_min-style) JSON box. Returns [x0,y0,x1,y1] or None."""
    if not text:
        return None
    m = BOX_RE.search(text)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    try:
        if all(k in d for k in ("x", "y", "w", "h")):
            x, y, w, h = (float(d["x"]), float(d["y"]), float(d["w"]), float(d["h"]))
            return [x, y, x + w, y + h]
        if all(k in d for k in ("x_min", "y_min", "x_max", "y_max")):
            return [float(d["x_min"]), float(d["y_min"]), float(d["x_max"]), float(d["y_max"])]
    except (TypeError, ValueError):
        return None
    return None


def iou(a, b):
    """Intersection-over-union of two [x0,y0,x1,y1] boxes (0-1000 scale)."""
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    bb = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = aa + bb - inter
    return round(inter / union, 3) if union > 0 else 0.0


def norm_ar(t):
    return re.sub(r"\s+", " ", (t or "").strip())


def judge_arabic(reply, keywords):
    """Pass iff every ground-truth keyword appears (substring, order-free)."""
    r = norm_ar(reply)
    hits = [k for k in keywords if k in r]
    return {
        "pass": len(hits) == len(keywords),
        "hits": hits,
        "missing": [k for k in keywords if k not in r],
    }


INT_RE = re.compile(r"-?\d+")


def judge_count(reply, expected):
    m = INT_RE.search(reply or "")
    got = int(m.group(0)) if m else None
    return {"pass": got == expected, "got": got, "expected": expected}


# ---------------- suite ----------------


def build_tests(gt):
    return [
        (
            "V1_ground_login",
            os.path.join(FIX_DIR, "ui_login.png"),
            P_GROUND.format(label="red LOGIN button"),
            ("ground", gt["ui_login.png"]["login_button"]["box"]),
        ),
        (
            "V2_ground_save",
            os.path.join(FIX_DIR, "ui_toolbar.png"),
            P_GROUND.format(label="blue SAVE button"),
            ("ground", gt["ui_toolbar.png"]["save_button"]["box"]),
        ),
        (
            "V3_arabic_read",
            os.path.join(FIX_DIR, "arabic_card.png"),
            P_ARABIC,
            ("arabic", gt["arabic_card.png"]["keywords"]),
        ),
        (
            "V4_count_circles",
            os.path.join(FIX_DIR, "grid_count.png"),
            P_COUNT.format(what="blue circles"),
            ("count", gt["grid_count.png"]["blue_circles"]),
        ),
        (
            "V5_count_toolbar_buttons",
            os.path.join(FIX_DIR, "ui_toolbar.png"),
            P_COUNT.format(what="buttons in the dark toolbar (excluding the search field)"),
            ("count", gt["ui_toolbar.png"]["toolbar_button_count"]),
        ),
        (
            "V6_count_red_squares",
            os.path.join(FIX_DIR, "grid_count.png"),
            P_COUNT.format(what="red squares (squares only, not circles)"),
            ("count", gt["grid_count.png"]["red_squares"]),
        ),
    ]


def run_one(chat, kind, target, prompt, image):
    try:
        text, secs, usage = chat(vision_messages(prompt, image), temp=TEMP, max_tokens=MAX_TOKENS)
    except Exception as e:
        msg = str(e)[:300]
        if NO_IMAGE_RE.search(msg):
            return {"pass": False, "error": "unsupported-image-call", "log": msg, "sample": ""}
        return {"pass": False, "error": msg, "sample": ""}
    rec = {"secs": round(secs, 1), "usage": usage, "sample": (text or "")[:600]}
    if kind == "ground":
        box = parse_box(text)
        if box is None:
            rec.update({"pass": False, "iou": 0.0, "log": "no parseable {x,y,w,h} box"})
        else:
            v = iou(box, target)
            rec.update(
                {
                    "pass": bool(v >= IOU_PASS),
                    "iou": v,
                    "pred": [round(x, 1) for x in box],
                    "expected": target,
                    "log": "iou=%.3f" % v,
                }
            )
    elif kind == "arabic":
        j = judge_arabic(text, target)
        rec.update({"pass": j["pass"], "log": "hits=%s missing=%s" % (j["hits"], j["missing"])})
    else:
        j = judge_count(text, target)
        rec.update({"pass": j["pass"], "log": "got=%s expected=%s" % (j["got"], j["expected"])})
    rec["error"] = None
    return rec


def _run_via_runner(args):
    """Thin compatibility wrapper over the unified runner (review P0-7).

    Same CLI flags; execution flows through runner.run_suite, so runs
    produce standard sealed raw bundles consumable by report_v2
    (invariants-gated). Gate denial becomes VOID attempts inside the
    bundle (executor-enforced), never a bespoke skip file.
    """
    import runner

    if (args.backend or "").lower() == "stub":
        chat = runner.stub_chat_factory("vision-compat")
    else:
        from backends import make_chat

        chat = make_chat(args.backend, args.base_url, args.model, args.api_key)
    only = [x.strip().upper() for x in args.only.split(",") if x.strip()]
    order = ["V1", "V2", "V3", "V4", "V5", "V6"]
    families = [v for v in order if (not only) or v in only] or None
    model_id = args.model or os.environ.get("MODEL", "model")
    rundir, summary = runner.run_suite(
        "vision",
        chat,
        model_id,
        args.backend,
        0,
        1,
        max(args.trials, 1),
        0.25,
        args.out,
        families=families,
        force=bool(args.force),
        # This entry IS the vision suite: running it asserts a
        # vision-capable model (the live image probe still gates
        # per-family VOIDs at execution time).
        model_modalities="text,vision",
    )
    print(
        "vision: suite=%s attempts=%d pass=%d"
        % (summary["suite"], summary["n_attempts"], summary["n_pass"])
    )
    print("saved", rundir)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="vision-bench runner (PROMPT_PACK vision-v1)")
    ap.add_argument("--backend", default=os.environ.get("BACKEND", "openai-generic"))
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--only", default="", help="comma list, e.g. V1,V3")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--out", default="results/")
    ap.add_argument(
        "--force",
        action="store_true",
        help="skip the image-support gate (failures then count as errors)",
    )
    ap.add_argument("--list", action="store_true", help="list tests, run nothing")
    args = ap.parse_args(argv)

    gt = load_ground_truth()
    tests = build_tests(gt)
    if args.list:
        for name, img, _p, _t in tests:
            print("%s  %s" % (name, os.path.basename(img)))
        return 0

    # P0-7: all execution flows through the unified runner.
    return _run_via_runner(args)


if __name__ == "__main__":
    sys.exit(main())
