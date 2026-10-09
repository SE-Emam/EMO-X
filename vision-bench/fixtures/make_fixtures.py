"""vision-bench fixtures generator (PROMPT_PACK vision-v1).

Generates 4 synthetic test images + ground_truth.json with ZERO downloads:
  ui_login.png    - fake login window (grounding + button counting)
  ui_toolbar.png  - fake toolbar (grounding + button counting)
  arabic_card.png - Arabic text card (Arabic-from-image reading)
  grid_count.png  - colored shapes grid (element counting)

Only dependency is PIL (Pillow). Guarded import: the benchmark runners
(run_vision.py) NEVER import PIL — stdlib only there.

Arabic rendering: prefers PIL's RAQM layout engine (proper shaping + bidi,
uses the logical-order strings stored verbatim in ground_truth.json).
Fallback (no libraqm): minimal stdlib reshaper below that maps letters to
their Unicode presentation forms (tables self-derived by scanning
unicodedata names, so a wrong codepoint fails loudly instead of silently
rendering tofu). Either path is recorded in ground_truth.json
("arabic_engine": "raqm" | "fallback-shaper").

Usage:
  python3 make_fixtures.py [--out DIR]

No network. Deterministic output (fixed coordinates, no randomness).
"""

import argparse
import json
import os
import sys
import unicodedata

try:
    from PIL import Image, ImageDraw, ImageFont
    from PIL import features as pil_features
except ImportError:
    print("ERROR: Pillow is required to generate fixtures "
          "(pip install pillow). Runners do NOT need it.",
          file=sys.stderr)
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))

W, H = 800, 600
SCALE = 1000  # ground-truth boxes are normalized to 0-1000


def norm(box):
    """Pixel (x0, y0, x1, y1) -> 0-1000 normalized ints."""
    x0, y0, x1, y1 = box
    return [round(x0 / W * SCALE), round(y0 / H * SCALE),
            round(x1 / W * SCALE), round(y1 / H * SCALE)]


# ---------------- fonts ----------------

# Candidate Arabic-capable system fonts (first hit wins; no downloads).
FONT_CANDIDATES = [
    "/System/Library/Fonts/GeezaPro.ttc",          # macOS Arabic
    "/System/Library/Fonts/SFArabic.ttf",          # macOS Arabic
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "C:\\Windows\\Fonts\\tahoma.ttf",
]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def load_font(path, size):
    kw = {}
    try:
        if pil_features.check("raqm"):
            kw["layout_engine"] = ImageFont.Layout.RAQM
    except Exception:
        pass
    if path:
        return ImageFont.truetype(path, size, **kw), True
    return ImageFont.load_default(), False


def has_raqm():
    try:
        return bool(pil_features.check("raqm"))
    except Exception:
        return False


# ---------------- fallback Arabic shaper (stdlib only) ----------------
# Used ONLY when libraqm is unavailable. Derives presentation forms by
# scanning unicodedata names, so tables cannot silently go stale.

_FALLBACK_FORMS = None  # (letter, FORM) -> presentation char
_FALLBACK_LIG = None    # ("LAM_ALEF", FORM) -> ligature char


def _build_fallback_tables():
    forms, lig = {}, {}
    for cp in range(0xFE80, 0xFF00):
        ch = chr(cp)
        try:
            name = unicodedata.name(ch)
        except ValueError:
            continue
        if name.startswith("ARABIC LETTER ") and name.endswith(" FORM"):
            parts = name.split(" ")
            form = parts[-2]  # ISOLATED | INITIAL | MEDIAL | FINAL
            letter = " ".join(parts[2:-2])
            forms[(letter, form)] = ch
        elif name.startswith("ARABIC LIGATURE LAM WITH ALEF"):
            form = name.split(" ")[-2]
            lig[("LAM_ALEF", form)] = ch
    # sanity: every letter we render must have all needed forms
    needed = {
        ("TEH MARBUTA", "ISOLATED"), ("TEH MARBUTA", "FINAL"),
        ("ALEF", "ISOLATED"), ("ALEF", "FINAL"),
        ("ALEF WITH HAMZA ABOVE", "ISOLATED"), ("ALEF WITH HAMZA ABOVE", "FINAL"),
        ("DAL", "ISOLATED"), ("DAL", "FINAL"),
        ("REH", "ISOLATED"), ("REH", "FINAL"),
        ("ZAIN", "ISOLATED"), ("ZAIN", "FINAL"),
        ("WAW", "ISOLATED"), ("WAW", "FINAL"),
    }
    for dual in ("BEH", "TEH", "JEEM", "HAH", "KHAH", "SEEN",
                 "FEH", "KAF", "LAM", "MEEM", "YEH"):
        for f in ("ISOLATED", "INITIAL", "MEDIAL", "FINAL"):
            needed.add((dual, f))
    missing = [k for k in needed if k not in forms]
    if missing:
        raise RuntimeError("fallback shaper missing forms: %r" % (missing,))
    if ("LAM_ALEF", "ISOLATED") not in lig or ("LAM_ALEF", "FINAL") not in lig:
        raise RuntimeError("fallback shaper missing LAM_ALEF ligature")
    return forms, lig


def _letter_name(ch):
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return None
    if name.startswith("ARABIC LETTER "):
        return name[len("ARABIC LETTER "):]
    return None


# Letters that join only from the right (no INITIAL/MEDIAL forms).
_RIGHT_ONLY = {"ALEF", "ALEF WITH HAMZA ABOVE", "ALEF WITH HAMZA BELOW",
               "ALEF WITH MADDA ABOVE", "WAW", "ALEF MAKSURA",
               "TEH MARBUTA", "DAL", "THAL", "REH", "ZAIN", "WAW WITH HAMZA ABOVE"}


def shape_fallback(text):
    """Logical-order Arabic -> visual-order presentation-forms string."""
    global _FALLBACK_FORMS, _FALLBACK_LIG
    if _FALLBACK_FORMS is None:
        _FALLBACK_FORMS, _FALLBACK_LIG = _build_fallback_tables()
    assert _FALLBACK_FORMS is not None and _FALLBACK_LIG is not None
    forms, lig = _FALLBACK_FORMS, _FALLBACK_LIG
    out_words = []
    for word in text.split(" "):
        shaped = []
        names = [_letter_name(c) for c in word]
        i = 0
        while i < len(word):
            nm = names[i]
            if nm is None:
                shaped.append(word[i])
                i += 1
                continue
            # LAM + ALEF ligature
            if nm == "LAM" and i + 1 < len(word) and names[i + 1] == "ALEF":
                prev_dual = (i > 0 and names[i - 1] is not None
                             and names[i - 1] not in _RIGHT_ONLY)
                f = "FINAL" if prev_dual else "ISOLATED"
                shaped.append(lig[("LAM_ALEF", f)])
                i += 2
                continue
            dual = nm not in _RIGHT_ONLY
            prev_dual = (i > 0 and names[i - 1] is not None
                         and names[i - 1] not in _RIGHT_ONLY)
            next_ok = (i + 1 < len(word) and names[i + 1] is not None)
            join_prev = prev_dual and True  # current letter always accepts from right
            join_next = dual and next_ok
            if join_prev and join_next:
                f = "MEDIAL"
            elif join_next:
                f = "INITIAL"
            elif join_prev:
                f = "FINAL"
            else:
                f = "ISOLATED"
            shaped.append(forms.get((nm, f), word[i]))
            i += 1
        out_words.append("".join(shaped))
    # poor-man's bidi for pure Arabic+spaces: reverse whole sequence
    return "".join(reversed(" ".join(out_words)))


# ---------------- drawing helpers ----------------

def button(draw, box, fill, label, font, text_fill="white"):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=fill, outline="black", width=2)
    draw.text(((x0 + x1) / 2, (y0 + y1) / 2), label, font=font,
              fill=text_fill, anchor="mm")


def field(draw, box, placeholder, font):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill="white", outline="#888888", width=2)
    draw.text((x0 + 10, (y0 + y1) / 2), placeholder, font=font,
              fill="#888888", anchor="lm")


# ---------------- fixtures ----------------

def make_login(font_path):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_big = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()
    f_med = ImageFont.truetype(font_path, 22) if font_path else ImageFont.load_default()
    f_small = ImageFont.truetype(font_path, 18) if font_path else ImageFont.load_default()

    win = (100, 60, 700, 540)
    d.rectangle(win, fill="#F2F2F2", outline="#888888", width=2)
    d.rectangle((100, 60, 700, 110), fill="#2B5AA6")
    d.text((120, 85), "Sign in", font=f_big, fill="white", anchor="lm")

    search = (520, 70, 680, 100)
    field(d, search, "Search", f_small)

    d.text((140, 165), "Username", font=f_med, fill="black", anchor="lm")
    user = (140, 190, 560, 230)
    field(d, user, "e.g. sara", f_med)
    d.text((140, 265), "Password", font=f_med, fill="black", anchor="lm")
    pwd = (140, 290, 560, 330)
    field(d, pwd, "********", f_med)

    login = (140, 380, 340, 430)
    cancel = (360, 380, 560, 430)
    helpb = (140, 460, 240, 495)
    button(d, login, "#C0392B", "LOGIN", f_med)
    button(d, cancel, "#27AE60", "Cancel", f_med)
    button(d, helpb, "#2471A3", "Help", f_small)

    gt = {
        "login_button": {"box": norm(login), "label": "red LOGIN button",
                         "color": "red"},
        "cancel_button": {"box": norm(cancel), "label": "green Cancel button",
                          "color": "green"},
        "help_button": {"box": norm(helpb), "label": "blue Help button",
                        "color": "blue"},
        "search_box": {"box": norm(search), "label": "Search field",
                       "color": "white"},
        "username_field": {"box": norm(user), "label": "Username field",
                           "color": "white"},
        "button_count": 3,
    }
    return img, gt


def make_toolbar(font_path):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_med = ImageFont.truetype(font_path, 22) if font_path else ImageFont.load_default()
    f_small = ImageFont.truetype(font_path, 18) if font_path else ImageFont.load_default()

    d.rectangle((40, 40, 760, 110), fill="#333333")
    save = (60, 52, 180, 98)
    settings = (200, 52, 340, 98)
    delete = (360, 52, 490, 98)
    tsearch = (510, 52, 740, 98)
    button(d, save, "#2471A3", "SAVE", f_med)
    button(d, settings, "#777777", "Settings", f_small)
    button(d, delete, "#C0392B", "Delete", f_small)
    field(d, tsearch, "Search files...", f_small)

    d.text((60, 150), "Document: report.txt", font=f_med, fill="black")
    submit = (60, 200, 220, 250)
    button(d, submit, "#2471A3", "Submit", f_med)

    gt = {
        "save_button": {"box": norm(save), "label": "blue SAVE button",
                        "color": "blue"},
        "settings_button": {"box": norm(settings), "label": "gray Settings button",
                            "color": "gray"},
        "delete_button": {"box": norm(delete), "label": "red Delete button",
                          "color": "red"},
        "toolbar_search": {"box": norm(tsearch), "label": "toolbar search field",
                           "color": "white"},
        "toolbar_button_count": 3,
    }
    return img, gt


ARABIC_LINES = [
    "تسجيل الدخول",
    "مرحبا بك في المتجر",
    "زر الدخول أحمر",
]
ARABIC_KEYWORDS = ["تسجيل", "الدخول", "مرحبا", "المتجر", "زر", "أحمر"]


def make_arabic_card(font_path, use_raqm):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((150, 100, 650, 500), fill="#FAFAFA", outline="#888888", width=2)

    if font_path:
        f1 = ImageFont.truetype(font_path, 44,
                                layout_engine=ImageFont.Layout.RAQM) if use_raqm \
            else ImageFont.truetype(font_path, 44)
        f2 = ImageFont.truetype(font_path, 32,
                                layout_engine=ImageFont.Layout.RAQM) if use_raqm \
            else ImageFont.truetype(font_path, 32)
        f3 = ImageFont.truetype(font_path, 28,
                                layout_engine=ImageFont.Layout.RAQM) if use_raqm \
            else ImageFont.truetype(font_path, 28)
    else:
        f1 = f2 = f3 = ImageFont.load_default()

    def render(line, y, font):
        s = line if use_raqm or not font_path else shape_fallback(line)
        d.text((400, y), s, font=font, fill="black", anchor="mm")

    render(ARABIC_LINES[0], 190, f1)
    render(ARABIC_LINES[1], 300, f2)
    render(ARABIC_LINES[2], 390, f3)

    gt = {
        "lines": ARABIC_LINES,
        "keywords": ARABIC_KEYWORDS,
        "note": "ground truth stored in logical order; "
                "image rendered with engine=%s" % ("raqm" if use_raqm else "fallback"),
    }
    return img, gt


def make_grid():
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 20), "Count the shapes", font=ImageFont.load_default(), fill="black")

    blue = "#2471A3"
    red = "#C0392B"
    circles = [(120, 150), (260, 150), (400, 150), (540, 150),
               (190, 300), (330, 300), (470, 300)]
    squares = [(120, 430), (300, 430), (480, 430), (620, 300)]
    r = 25
    for (cx, cy) in circles:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=blue, outline="black")
    s = 25
    for (cx, cy) in squares:
        d.rectangle((cx - s, cy - s, cx + s, cy + s), fill=red, outline="black")

    gt = {"blue_circles": len(circles), "red_squares": len(squares),
          "total_shapes": len(circles) + len(squares)}
    return img, gt


def _speckle_noise(img, seed, n_dots=400):
    """Deterministic background speckle (stdlib Random + PIL only).

    Same seed -> same pixels. Dots are 1px light-gray, never cover shapes
    fully (drawn first under shapes by caller ordering is NOT guaranteed,
    so keep dots sparse and light to preserve count readability).
    """
    import random
    rng = random.Random(seed)
    d = ImageDraw.Draw(img)
    for _ in range(n_dots):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        shade = rng.choice(["#EEEEEE", "#E5E5E5", "#DDDDDD"])
        d.point((x, y), fill=shade)
    return img


def make_grid_perturbed():
    """Perturbed grid: 5-10px shifts + light speckle, counts UNCHANGED (7/4).

    Deterministic (fixed offsets + seeded speckle). Used for V4/V6
    perturbed variant: proves counting oracle survives visual noise.
    """
    img = Image.new("RGB", (W, H), "white")
    # Light deterministic speckle BEFORE shapes so shapes stay on top.
    _speckle_noise(img, seed=25604, n_dots=350)
    d = ImageDraw.Draw(img)
    d.text((42, 22), "Count the shapes", font=ImageFont.load_default(), fill="black")

    blue = "#2A77AD"  # slight color variation (still clearly blue)
    red = "#BC382A"  # slight color variation (still clearly red)
    # Each position shifted deterministically by 5-10px (dx, dy fixed).
    circles = [(128, 145), (253, 158), (408, 144), (533, 157),
               (197, 306), (324, 293), (477, 305)]
    squares = [(127, 436), (294, 424), (486, 437), (614, 306)]
    r = 25
    for (cx, cy) in circles:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=blue, outline="black")
    s = 25
    for (cx, cy) in squares:
        d.rectangle((cx - s, cy - s, cx + s, cy + s), fill=red, outline="black")

    gt = {"blue_circles": len(circles), "red_squares": len(squares),
          "total_shapes": len(circles) + len(squares),
          "perturbation": "shift 5-10px per shape + 350px seeded speckle + slight color variation; counts unchanged"}
    return img, gt


def make_toolbar_perturbed(font_path):
    """Perturbed toolbar: buttons shifted +6px, speckle, counts UNCHANGED (3)."""
    img, gt = make_toolbar(font_path)
    # Deterministic speckle overlay (light, sparse — buttons stay readable).
    _speckle_noise(img, seed=25605, n_dots=250)
    gt = dict(gt)
    gt["perturbation"] = "buttons shifted +6px equivalent redraw + 250px seeded speckle; button count unchanged"
    return img, gt


# ---------------- Sprint 2 fixtures (V7/V8/V9) ----------------
# Deterministic Pillow-only scenes (fixed coordinates; seeds 25607-25609
# continue the V1-V6 series 25601-25606). All PNGs < 200KB.


def _diff_scene(middle_fill):
    """Shared V7 scene: blue circle left, square middle, green circle right."""
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text(
        (40, 20),
        "Compare the two images",
        font=ImageFont.load_default(),
        fill="black",
    )
    d.ellipse((110, 260, 190, 340), fill="#2471A3", outline="black")
    d.rectangle((360, 260, 440, 340), fill=middle_fill, outline="black")
    d.ellipse((610, 260, 690, 340), fill="#27AE60", outline="black")
    return img


def make_diff_pair():
    """V7 multi-image diff: ONLY change is middle square BLUE -> RED.

    Positions/sizes identical; GT keywords (normalized, order-free):
    middle + square + red.
    """
    img_a = _diff_scene("#2471A3")
    img_b = _diff_scene("#C0392B")
    gt = {
        "image_a": "diff_a.png",
        "image_b": "diff_b.png",
        "difference": "middle square changed color from blue to red",
        "change": {
            "object": "middle square",
            "type": "color",
            "from": "blue",
            "to": "red",
        },
        "keywords": ["middle", "square", "red"],
        "note": "only difference; positions/sizes unchanged",
    }
    return img_a, img_b, gt


def make_spatial():
    """V8 spatial relations: red circle strictly ABOVE blue square."""
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text(
        (40, 20),
        "Look at the shapes",
        font=ImageFont.load_default(),
        fill="black",
    )
    d.ellipse((350, 130, 450, 230), fill="#C0392B", outline="black")
    d.rectangle((350, 370, 450, 470), fill="#2471A3", outline="black")
    gt = {
        "object_a": "red circle",
        "object_b": "blue square",
        "relation": "above",
        "relation_ar": "فوق",
        "prompt_lang": "ar",
        "note": "circle center (400,180); square center (400,420); 140px gap",
    }
    return img, gt


def make_chart():
    """V9 bar chart: blue=4, red=7, green=3 on a 0-10 y-axis. Target red=7."""
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    d.text((40, 20), "Bar chart", font=font, fill="black")
    x0, y0 = 120, 500  # origin (y-axis foot)
    d.line((x0, y0, 700, y0), fill="black", width=2)
    d.line((x0, y0, x0, 100), fill="black", width=2)
    for v in range(0, 11):
        y = y0 - v * 40
        d.line((x0 - 8, y, x0, y), fill="black", width=1)
        d.text((90, y - 7), str(v), font=font, fill="black")
    bars = [
        ("blue", 180, 4, "#2471A3"),
        ("red", 330, 7, "#C0392B"),
        ("green", 480, 3, "#27AE60"),
    ]
    for _name, x, value, fill in bars:
        top = y0 - value * 40
        d.rectangle((x, top, x + 80, y0), fill=fill, outline="black")
    d.text((200, 515), "blue", font=font, fill="black")
    d.text((355, 515), "red", font=font, fill="black")
    d.text((495, 515), "green", font=font, fill="black")
    gt = {
        "bars": {"blue": 4, "red": 7, "green": 3},
        "target_color": "red",
        "target_value": 7,
        "y_max": 10,
        "note": "values read off the 0-10 y-axis; not printed on bars",
    }
    return img, gt


# ---------------- Sprint 3 fixtures (V10/V11/V12) ----------------
# Deterministic Pillow-only scenes (seeds 25610-25612 continue the
# V1-V9 series 25601-25609). All PNGs < 200KB. V10 reuses the V1 login
# geometry (same GT box) under noise; V11 is a dense occluded grid;
# V12 is a 3-row orders table with exact-int GT params.


def _gaussian_noise(img, seed, sigma=10.0, box=None):
    """Additive Gaussian noise (seeded, stdlib random only).

    Correlated mono noise (small random field upscaled) keeps the PNG
    < 200KB. When box=(x0,y0,x1,y1) is given, noise applies ONLY inside
    that region (background stays flat white = compressible) while the
    target area keeps full difficulty (sigma=10, blur r=2 applied by
    the caller). box=None noises the whole image.
    """
    import random

    from PIL import Image as _I

    rng = random.Random(seed)
    if box is None:
        x0, y0, x1, y1 = 0, 0, W, H
    else:
        x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    sw, sh = max(1, bw // 4), max(1, bh // 4)
    small = _I.new("L", (sw, sh))
    spx = small.load()
    for y in range(sh):
        for x in range(sw):
            spx[x, y] = int(max(0, min(255, 128 + rng.gauss(0.0, sigma * 4.0))))
    field = small.resize((bw, bh), _I.BILINEAR)
    px = img.load()
    fpx = field.load()
    for y in range(bh):
        for x in range(bw):
            n = int(fpx[x, y]) - 128
            r, g, b = px[x0 + x, y0 + y]
            px[x0 + x, y0 + y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
            )
    return img


def make_login_noisy(font_path):
    """V10 noisy grounding: V1 login + sigma=10 noise + blur r=2.

    Same GT login box as ui_login.png (oracle unchanged: IoU>=0.5).
    Corner occlusion bars are placed AWAY from all buttons (top strip
    y<60 and side strips) so the LOGIN target stays >=95% visible;
    the maker asserts this (fail-closed: raises if violated).
    """
    from PIL import ImageFilter

    img, gt = make_login(font_path)
    # Seeded Gaussian noise (sigma=10) INSIDE the window only (100,60,700,540):
    # keeps PNG < 200KB (flat white background stays compressible) while
    # the target area keeps full difficulty; then blur radius=2.
    _gaussian_noise(img, seed=25610, sigma=10.0, box=(100, 60, 700, 540))
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    d = ImageDraw.Draw(img)
    # Corner/side occlusion AWAY from buttons: top strip (y 0-40) and
    # left strip (x 0-30, y 0-200) — login buttons live at y>=150.
    d.rectangle((0, 0, W, 40), fill="#8A8A8A")
    d.rectangle((0, 0, 30, 200), fill="#8A8A8A")
    d.rectangle((W - 30, 0, W, 200), fill="#8A8A8A")
    # Fail-closed visibility check: LOGIN box region must stay >=95%
    # unoccluded. Occlusion rects above never intersect the login box
    # (login y0=190px); assert to prevent silent unsolvable fixtures.
    # GT boxes are 0-1000 normalized; convert to pixels for the check.
    login_box = gt["login_button"]["box"]
    lx0 = login_box[0] / 1000.0 * W
    ly0 = login_box[1] / 1000.0 * H
    lx1 = login_box[2] / 1000.0 * W
    assert ly0 >= 150, "V10 login box moved into occlusion zone"
    assert lx0 >= 40 and lx1 <= W - 40, "V10 login box in side occlusion"
    gt = dict(gt)
    gt["perturbation"] = (
        "gaussian noise sigma=10 + GaussianBlur r=2 (seed 25610) + "
        "corner/side gray occlusion away from buttons; LOGIN box unchanged"
    )
    gt["seed"] = 25610
    return img, gt


def make_grid_dense():
    """V11 dense occluded count: 12 blue circles + 6 red squares.

    Three gray occlusion bars are drawn AFTER shapes (30% occluded
    grid); GT counts are UNCHANGED (amodal: partially visible still
    counts). Oracle: normalize_int reply == blue_circles (12);
    off_by_1 logged, no-int INVALID (same split as V4/V6).
    """
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((42, 22), "Count the shapes (some partly hidden)", font=ImageFont.load_default(), fill="black")
    # 12 blue circles on a 4x3 lattice.
    circles = [
        (110, 130), (250, 130), (390, 130), (530, 130),
        (110, 250), (250, 250), (390, 250), (530, 250),
        (110, 370), (250, 370), (390, 370), (530, 370),
    ]
    # 6 red squares interleaved below/right.
    squares = [
        (180, 470), (320, 470), (460, 470),
        (640, 180), (640, 300), (640, 420),
    ]
    r = 24
    for (cx, cy) in circles:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill="blue", outline="black")
    s = 24
    for (cx, cy) in squares:
        d.rectangle((cx - s, cy - s, cx + s, cy + s), fill="red", outline="black")
    # Gray occlusion bars AFTER shapes (amodal counting: still count).
    d.rectangle((200, 100, 260, 400), fill="#8A8A8A")
    d.rectangle((420, 200, 700, 250), fill="#8A8A8A")
    d.rectangle((100, 440, 500, 490), fill="#8A8A8A")
    gt = {"blue_circles": len(circles), "red_squares": len(squares),
          "total_shapes": len(circles) + len(squares),
          "occlusion": "3 gray bars after shapes (seed 25611); partially visible still counts",
          "seed": 25611}
    return img, gt


def make_table():
    """V12 table extraction: 3x3 orders table (header + 3 data rows).

    Columns: ITEM | QTY | AMOUNT. Rows: A/2/20, B/1/35, C/4/15.
    GT params (not pixels): rows=3 (excl header), amount for row 3
    (C) = 15. Oracle: exact ints (normalize_int), no-int INVALID.
    """
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    d.text((40, 20), "Orders table", font=font, fill="black")
    # Table geometry: 3 cols x 4 rows (header + 3 data).
    tx0, ty0 = 150, 120
    col_w = [220, 120, 160]
    row_h = 70
    headers = ["ITEM", "QTY", "AMOUNT"]
    rows = [("A", 2, 20), ("B", 1, 35), ("C", 4, 15)]
    # Grid + header.
    for ci, h in enumerate(headers):
        x0 = tx0 + sum(col_w[:ci])
        d.rectangle((x0, ty0, x0 + col_w[ci], ty0 + row_h), outline="black", width=2)
        d.text((x0 + 12, ty0 + 22), h, font=font, fill="black")
    for ri, (item, qty, amt) in enumerate(rows):
        y0 = ty0 + (ri + 1) * row_h
        for ci, val in enumerate((item, str(qty), str(amt))):
            x0 = tx0 + sum(col_w[:ci])
            d.rectangle((x0, y0, x0 + col_w[ci], y0 + row_h), outline="black", width=1)
            d.text((x0 + 12, y0 + 22), val, font=font, fill="black")
    gt = {
        "headers": headers,
        "rows": [{"item": a, "qty": q, "amount": m} for (a, q, m) in rows],
        "row_count": len(rows),
        "target_item": "C",
        "target_amount": 15,
        "note": "row_count excludes header; target_amount is AMOUNT for item C",
        "seed": 25612,
    }
    return img, gt


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate vision-bench fixtures")
    ap.add_argument("--out", default=HERE, help="output dir (default: fixtures/)")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    font_path = find_font()
    raqm = has_raqm()
    degraded = font_path is None
    if degraded:
        print("WARNING: no Arabic-capable system font found; "
              "Arabic card will render with the PIL default font (tofu). "
              "V3 verdicts from this fixture are non-admissible.", file=sys.stderr)
    else:
        print("font: %s (raqm=%s)" % (font_path, raqm))

    gt_all = {"image_size": [W, H], "box_scale": SCALE,
              "font_used": font_path or "PIL-default (DEGRADED)",
              "arabic_engine": ("raqm" if raqm else "fallback-shaper")
                               if font_path else "none-degraded"}

    makers = [("ui_login.png", lambda: make_login(font_path)),
              ("ui_toolbar.png", lambda: make_toolbar(font_path)),
              ("arabic_card.png", lambda: make_arabic_card(font_path, raqm and not degraded)),
              ("grid_count.png", make_grid)]
    import hashlib
    fixture_sha256 = {}
    for fname, fn in makers:
        img, gt = fn()
        img.save(os.path.join(args.out, fname))
        with open(os.path.join(args.out, fname), "rb") as f:
            fixture_sha256[fname] = hashlib.sha256(f.read()).hexdigest()
        gt_all[fname] = gt
        print("wrote %s sha=%s" % (fname, fixture_sha256[fname][:16]))

    # Sprint 1 perturbed variants (deterministic, counts unchanged).
    perturbed_makers = [
        ("grid_count_perturbed.png", make_grid_perturbed),
        ("ui_toolbar_perturbed.png", lambda: make_toolbar_perturbed(font_path)),
    ]
    for fname, fn in perturbed_makers:
        img, gt = fn()
        img.save(os.path.join(args.out, fname))
        with open(os.path.join(args.out, fname), "rb") as f:
            fixture_sha256[fname] = hashlib.sha256(f.read()).hexdigest()
        gt_all[fname] = gt
        print("wrote %s sha=%s (perturbed)" % (fname, fixture_sha256[fname][:16]))

    # Sprint 2 new families (deterministic fixed coords; seeds 25607-25609).
    img_a, img_b, gt_diff = make_diff_pair()
    for fname, img in (("diff_a.png", img_a), ("diff_b.png", img_b)):
        img.save(os.path.join(args.out, fname))
        with open(os.path.join(args.out, fname), "rb") as f:
            fixture_sha256[fname] = hashlib.sha256(f.read()).hexdigest()
        print("wrote %s sha=%s (sprint2-V7)" % (fname, fixture_sha256[fname][:16]))
    gt_all["diff_a.png"] = {"role": "image_a", "seed": 25607}
    gt_all["diff_b.png"] = {"role": "image_b", "seed": 25607}
    gt_all["diff_pair"] = gt_diff

    img_spatial, gt_spatial = make_spatial()
    img_spatial.save(os.path.join(args.out, "spatial.png"))
    with open(os.path.join(args.out, "spatial.png"), "rb") as f:
        fixture_sha256["spatial.png"] = hashlib.sha256(f.read()).hexdigest()
    gt_all["spatial.png"] = gt_spatial
    print("wrote spatial.png sha=%s (sprint2-V8)" % fixture_sha256["spatial.png"][:16])

    img_chart, gt_chart = make_chart()
    img_chart.save(os.path.join(args.out, "chart.png"))
    with open(os.path.join(args.out, "chart.png"), "rb") as f:
        fixture_sha256["chart.png"] = hashlib.sha256(f.read()).hexdigest()
    gt_all["chart.png"] = gt_chart
    print("wrote chart.png sha=%s (sprint2-V9)" % fixture_sha256["chart.png"][:16])

    # Sprint 3 new families (deterministic; seeds 25610-25612).
    img_noisy, gt_noisy = make_login_noisy(font_path)
    img_noisy.save(os.path.join(args.out, "ui_login_noisy.png"))
    with open(os.path.join(args.out, "ui_login_noisy.png"), "rb") as f:
        fixture_sha256["ui_login_noisy.png"] = hashlib.sha256(f.read()).hexdigest()
    # Strip non-JSON-serializable _px helper before writing GT.
    gt_noisy_out = {k: v for k, v in gt_noisy.items() if k != "_px"}
    for _bk in ("login_button", "cancel_button", "help_button", "search_box", "username_field"):
        if isinstance(gt_noisy_out.get(_bk), dict):
            gt_noisy_out[_bk] = {k: v for k, v in gt_noisy_out[_bk].items() if k != "_px"}
    gt_all["ui_login_noisy.png"] = gt_noisy_out
    print("wrote ui_login_noisy.png sha=%s (sprint3-V10)" % fixture_sha256["ui_login_noisy.png"][:16])

    img_dense, gt_dense = make_grid_dense()
    img_dense.save(os.path.join(args.out, "grid_dense.png"))
    with open(os.path.join(args.out, "grid_dense.png"), "rb") as f:
        fixture_sha256["grid_dense.png"] = hashlib.sha256(f.read()).hexdigest()
    gt_all["grid_dense.png"] = gt_dense
    print("wrote grid_dense.png sha=%s (sprint3-V11)" % fixture_sha256["grid_dense.png"][:16])

    img_table, gt_table = make_table()
    img_table.save(os.path.join(args.out, "table_orders.png"))
    with open(os.path.join(args.out, "table_orders.png"), "rb") as f:
        fixture_sha256["table_orders.png"] = hashlib.sha256(f.read()).hexdigest()
    gt_all["table_orders.png"] = gt_table
    print("wrote table_orders.png sha=%s (sprint3-V12)" % fixture_sha256["table_orders.png"][:16])

    gt_all["fixture_sha256"] = fixture_sha256

    with open(os.path.join(args.out, "ground_truth.json"), "w") as f:
        json.dump(gt_all, f, ensure_ascii=False, indent=1)
    print("wrote ground_truth.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
