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
# Sprint 2 frozen prompts (PROMPT_PACK vision-v1 extension, byte-frozen).
P_DIFF = (
    "Compare Image 1 and Image 2. What is the single difference between them? "
    "Reply with ONLY a short phrase naming the difference, no explanation."
)
P_SPATIAL_AR = (
    "صف موضع الدائرة الحمراء بالنسبة إلى المربع الأزرق. "
    "أجب بكلمة واحدة فقط من هذه الكلمات: فوق، تحت، يسار، يمين."
)
P_CHART = (
    "What is the exact integer value of the {color} bar in the chart? "
    "Reply with ONLY a single integer, no explanation."
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


# Sprint 2: multi-image messages (V7 image_count=2). Ordered parts with
# explicit Image 1 / Image 2 labels so the model can reference them.
# Fail-closed size guard: total raw payload > ~5MB -> caller VOIDs.
VISION_MULTI_MAX_BYTES = 5 * 1024 * 1024


def vision_messages_multi(prompt, image_paths):
    content = [{"type": "text", "text": prompt}]
    for i, path in enumerate(image_paths, start=1):
        content.append({"type": "text", "text": "Image %d:" % i})
        content.append({"type": "image_url", "image_url": {"url": img_data_url(path)}})
    return [{"role": "user", "content": content}]


def multi_payload_bytes(image_paths):
    total = 0
    for path in image_paths:
        try:
            total += os.path.getsize(path)
        except OSError:
            total += 10**9
    return total


# Sprint 1: canonical -> perturbed fixture routing (counting only).
# Returns the perturbed image path for a canonical path, or None when the
# family has no perturbed variant. Count GT is UNCHANGED under perturbation.
PERTURBED_IMAGE_MAP = {
    "grid_count.png": "grid_count_perturbed.png",
    "ui_toolbar.png": "ui_toolbar_perturbed.png",
}


def perturbed_image_for(image_path):
    """Map a canonical fixture path to its perturbed sibling (or None)."""
    base = os.path.basename(image_path or "")
    pert = PERTURBED_IMAGE_MAP.get(base)
    if not pert:
        return None
    cand = os.path.join(os.path.dirname(image_path), pert)
    return cand if os.path.isfile(cand) else os.path.join(FIX_DIR, pert)


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


# --- Sprint 1 normalization utils (mirrors shared/scoring.py, stdlib only) ---


def normalize_arabic(text):
    """Normalize Arabic for robust deterministic substring matching."""
    import unicodedata

    if text is None:
        return ""
    s = str(text)
    s = re.sub("[ً-ْٰـ]", "", s)
    s = re.sub("[آأإٱ]", "ا", s)
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


_EN_WORD_NUMS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

_AR_WORD_NUMS = {
    "صفر": 0,
    "واحد": 1,
    "واحده": 1,
    "احد": 1,
    "اثنان": 2,
    "اثنين": 2,
    "اثنتان": 2,
    "اثنتين": 2,
    "ثلاثه": 3,
    "ثلاث": 3,
    "اربعه": 4,
    "اربع": 4,
    "خمسه": 5,
    "خمس": 5,
    "سته": 6,
    "ست": 6,
    "سبعه": 7,
    "سبع": 7,
    "ثمانيه": 8,
    "ثماني": 8,
    "ثمان": 8,
    "تسعه": 9,
    "تسع": 9,
    "عشره": 10,
    "عشر": 10,
    "عشرون": 20,
    "عشرين": 20,
}


def _arabic_indic_to_ascii(s):
    out = []
    for ch in s:
        o = ord(ch)
        if 0x0660 <= o <= 0x0669:
            out.append(str(o - 0x0660))
        elif 0x06F0 <= o <= 0x06F9:
            out.append(str(o - 0x06F0))
        else:
            out.append(ch)
    return "".join(out)


def normalize_int(text):
    """Parse count reply to int: digits, EN words, AR words. None if absent."""
    if text is None:
        return None
    s = str(text)
    s_ascii = _arabic_indic_to_ascii(s)
    m = re.search(r"-?\d+", s_ascii)
    if m:
        try:
            return int(m.group(0))
        except ValueError:
            pass
    low = s_ascii.lower()
    for word in sorted(_EN_WORD_NUMS, key=len, reverse=True):
        if re.search(r"\b%s\b" % re.escape(word), low):
            return _EN_WORD_NUMS[word]
    norm = normalize_arabic(s_ascii)
    for word in sorted(_AR_WORD_NUMS, key=len, reverse=True):
        if word in norm:
            return _AR_WORD_NUMS[word]
    return None


def iou_tier(iou_value):
    """Return highest passed IoU tier in (0.9, 0.7, 0.5) or 0.0."""
    try:
        v = float(iou_value)
    except (TypeError, ValueError):
        return 0.0
    for tier in (0.9, 0.7, 0.5):
        if v >= tier:
            return tier
    return 0.0


def judge_arabic(reply, keywords):
    """Pass iff every keyword appears (normalized substring, order-free)."""
    r = normalize_arabic(reply)
    hits = [k for k in keywords if normalize_arabic(k) in r]
    return {
        "pass": len(hits) == len(keywords),
        "hits": hits,
        "missing": [k for k in keywords if normalize_arabic(k) not in r],
    }


INT_RE = re.compile(r"-?\d+")


# ---------------- Sprint 2 judges (deterministic, no LLM-judge) ----------------

# V7: accepted content words per GT keyword (normalized EN substring match).
# GT keywords: middle + square + red. Each must appear via an alias.
V7_KEYWORD_ALIASES = {
    "middle": ("middle", "center", "centre"),
    "square": ("square", "box", "rectangle"),
    "red": ("red",),
}


def judge_diff(reply, keywords):
    """Pass iff every GT keyword (or alias) appears normalized, order-free.

    Hallucinated differences (wrong color/object with no GT hit) fail
    closed as WRONG_RESULT. "No difference" with zero hits fails too.
    """
    r = (reply or "").lower()
    r = re.sub(r"\s+", " ", r).strip()
    hits = []
    missing = []
    for kw in keywords:
        aliases = V7_KEYWORD_ALIASES.get(kw, (kw,))
        if any(a in r for a in aliases):
            hits.append(kw)
        else:
            missing.append(kw)
    return {"pass": len(missing) == 0, "hits": hits, "missing": missing}


# V8: strict preposition check (EN + AR). Arabic prompt -> Arabic answer
# expected, but EN equivalents accepted (normalized, word-boundary for EN).
V8_RELATIONS = {
    "above": ("above", "over", "on top", "فوق", "فوقه", "اعلى", "أعلى"),
    "below": ("below", "under", "beneath", "تحت", "تحته", "اسفل", "أسفل"),
    "left": ("left", "left of", "يسار", "شمال"),
    "right": ("right", "right of", "يمين"),
}


def judge_spatial(reply, expected):
    """Pass iff the expected relation (or alias) appears, and NO competing
    relation appears. Competing preposition -> WRONG_RESULT (hallucination).
    """
    r_norm = normalize_arabic(reply)
    r_low = (reply or "").lower()
    exp_aliases = V8_RELATIONS.get(expected, (expected,))
    found_expected = any(
        (a in r_norm)
        if any("\u0600" <= c <= "\u06ff" for c in a)
        else re.search(r"\b%s\b" % re.escape(a), r_low)
        for a in exp_aliases
    )
    competing = []
    for rel, aliases in V8_RELATIONS.items():
        if rel == expected:
            continue
        for a in aliases:
            if any("\u0600" <= c <= "\u06ff" for c in a):
                if a in r_norm:
                    competing.append(rel)
                    break
            elif re.search(r"\b%s\b" % re.escape(a), r_low):
                competing.append(rel)
                break
    ok = bool(found_expected) and not competing
    return {"pass": ok, "found": found_expected, "competing": competing}


def judge_chart(reply, expected):
    """Pass iff normalize_int(reply) equals expected exactly (Sprint 1 util).

    Mirrors judge_count semantics: off_by_1 + invalid flags for the
    executor's INVALID_NO_INT vs WRONG_RESULT (off_by_1) split.
    """
    got = normalize_int(reply)
    off_by_one = got is not None and isinstance(expected, int) and abs(got - expected) == 1
    return {
        "pass": got == expected,
        "got": got,
        "expected": expected,
        "off_by_one": off_by_one,
        "invalid": got is None,
    }


def judge_count(reply, expected):
    got = normalize_int(reply)
    off_by_one = got is not None and isinstance(expected, int) and abs(got - expected) == 1
    return {
        "pass": got == expected,
        "got": got,
        "expected": expected,
        "off_by_one": off_by_one,
        "invalid": got is None,
    }


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
        # Sprint 2: V7 multi-image diff (image_count=2). img is a [a, b] list;
        # executor routes lists via vision_messages_multi + 5MB fail-closed guard.
        (
            "V7_diff_pair",
            [os.path.join(FIX_DIR, "diff_a.png"), os.path.join(FIX_DIR, "diff_b.png")],
            P_DIFF,
            ("diff", gt["diff_pair"]["keywords"]),
        ),
        # Sprint 2: V8 spatial relation (single image, Arabic prompt).
        (
            "V8_spatial_above",
            os.path.join(FIX_DIR, "spatial.png"),
            P_SPATIAL_AR,
            ("spatial", gt["spatial.png"]["relation"]),
        ),
        # Sprint 2: V9 chart reading (single image, exact int).
        (
            "V9_chart_red",
            os.path.join(FIX_DIR, "chart.png"),
            P_CHART.format(color=gt["chart.png"]["target_color"]),
            ("chart", gt["chart.png"]["target_value"]),
        ),
    ]


def run_one_multi(chat, kind, target, prompt, images):
    """Multi-image call (Sprint 2 V7). Fail-closed size guard.

    Total raw payload > VISION_MULTI_MAX_BYTES -> VOID record (never FAIL
    or ERROR for the model). Otherwise chats via vision_messages_multi and
    judges with the deterministic kind oracle.
    """
    if multi_payload_bytes(images) > VISION_MULTI_MAX_BYTES:
        return {
            "pass": False,
            "void": True,
            "log": "multi-image payload too large",
            "sample": "",
            "error": None,
        }
    try:
        text, secs, usage = chat(
            vision_messages_multi(prompt, images), temp=TEMP, max_tokens=MAX_TOKENS
        )
    except Exception as e:
        msg = str(e)[:300]
        if NO_IMAGE_RE.search(msg):
            return {"pass": False, "error": "unsupported-image-call", "log": msg, "sample": ""}
        return {"pass": False, "error": msg, "sample": ""}
    rec = {"secs": round(secs, 1), "usage": usage, "sample": (text or "")[:600]}
    if kind == "diff":
        j = judge_diff(text, target)
        rec.update({"pass": j["pass"], "log": "hits=%s missing=%s" % (j["hits"], j["missing"])})
    elif kind == "spatial":
        j = judge_spatial(text, target)
        rec.update(
            {"pass": j["pass"], "log": "found=%s competing=%s" % (j["found"], j["competing"])}
        )
    elif kind == "chart":
        j = judge_chart(text, target)
        if j.get("invalid"):
            rec.update(
                {
                    "pass": False,
                    "invalid": True,
                    "off_by_one": False,
                    "log": "got=%s expected=%s INVALID_NO_INT" % (j["got"], j["expected"]),
                }
            )
        elif j.get("off_by_one"):
            rec.update(
                {
                    "pass": False,
                    "off_by_one": True,
                    "log": "got=%s expected=%s WRONG_RESULT (off_by_1)" % (j["got"], j["expected"]),
                }
            )
        else:
            rec.update({"pass": j["pass"], "log": "got=%s expected=%s" % (j["got"], j["expected"])})
    else:
        rec.update({"pass": False, "log": "unknown multi kind %r" % (kind,)})
    rec["error"] = None
    return rec


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
            rec.update(
                {"pass": False, "iou": 0.0, "iou_tier": 0.0, "log": "no parseable {x,y,w,h} box"}
            )
        else:
            v = iou(box, target)
            rec.update(
                {
                    "pass": bool(v >= IOU_PASS),
                    "iou": v,
                    "iou_tier": iou_tier(v),
                    "pred": [round(x, 1) for x in box],
                    "expected": target,
                    "log": "iou=%.3f tier=%s" % (v, iou_tier(v)),
                }
            )
    elif kind == "arabic":
        j = judge_arabic(text, target)
        rec.update({"pass": j["pass"], "log": "hits=%s missing=%s" % (j["hits"], j["missing"])})
    elif kind == "diff":
        # Sprint 2 V7 via single-image path (should not happen; multi uses run_one_multi).
        j = judge_diff(text, target)
        rec.update({"pass": j["pass"], "log": "hits=%s missing=%s" % (j["hits"], j["missing"])})
    elif kind == "spatial":
        # Sprint 2 V8: strict preposition (competing relation -> WRONG_RESULT).
        j = judge_spatial(text, target)
        rec.update(
            {"pass": j["pass"], "log": "found=%s competing=%s" % (j["found"], j["competing"])}
        )
    elif kind == "chart":
        # Sprint 2 V9: exact int (mirrors count INVALID vs off_by_1 split).
        j = judge_chart(text, target)
        if j.get("invalid"):
            rec.update(
                {
                    "pass": False,
                    "invalid": True,
                    "off_by_one": False,
                    "log": "got=%s expected=%s INVALID_NO_INT" % (j["got"], j["expected"]),
                }
            )
        elif j.get("off_by_one"):
            rec.update(
                {
                    "pass": False,
                    "off_by_one": True,
                    "log": "got=%s expected=%s WRONG_RESULT (off_by_1)" % (j["got"], j["expected"]),
                }
            )
        else:
            rec.update({"pass": j["pass"], "log": "got=%s expected=%s" % (j["got"], j["expected"])})
    else:
        j = judge_count(text, target)
        if j.get("invalid"):
            rec.update(
                {
                    "pass": False,
                    "invalid": True,
                    "off_by_one": False,
                    "log": "got=%s expected=%s INVALID_NO_INT" % (j["got"], j["expected"]),
                }
            )
        elif j.get("off_by_one"):
            rec.update(
                {
                    "pass": False,
                    "off_by_one": True,
                    "log": "got=%s expected=%s WRONG_RESULT (off_by_1)" % (j["got"], j["expected"]),
                }
            )
        else:
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
    order = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9"]
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
            if isinstance(img, (list, tuple)):
                print("%s  %s" % (name, ",".join(os.path.basename(p) for p in img)))
            else:
                print("%s  %s" % (name, os.path.basename(img)))
        return 0

    # P0-7: all execution flows through the unified runner.
    return _run_via_runner(args)


if __name__ == "__main__":
    sys.exit(main())
