---
name: vision-bench
description: اختبارات الرؤية V1-V5 — تأريض عناصر UI (IoU)، قراءة عربي من صورة، عدّ عناصر؛ مرفوضة بسلاسة إن كان الـ endpoint بلا دعم صور. استخدمها لمقارنة قدرات VLM قبل اعتمادها.
---

# اختبار الرؤية (vision-bench) — V1–V5

## ما هذا؟

حزمة Phase 3 من EMO-X (خطة `PLAN.md` §3.4). تقيس **الرؤية**،
لا الكود: هل يحدد الموديل مكان عنصر UI (تأريض OSWorld-G/ScreenSpot-style)؟
هل يقرأ عربياً من صورة؟ هل يعدّ العناصر؟ كل الصور اصطناعية 100%
(مولّدة بـ `fixtures/make_fixtures.py`، بلا علامات حقيقية ولا بيانات حقيقية).

## البوابة (gating — اقرأ قبل التشغيل)

هذه الحزمة **مشروطة بوجود endpoint متعدد الوسائط**. المشغّل
`run_vision.py` يرفض بسلاسة (لا يفشل، لا يخترع نتائج) عندما تنعدم قدرة الصور:

1. فحص best-effort لـ `GET {base}/models` بحثاً عن آثار بصرية
   (`vision`, `vl`, `gpt-4o`, `gemini` …) — إشارة ضعيفة فقط.
2. **الفحص المُلزم:** استدعاء probe بصورة 1×1 قبل الحزمة؛ أي رفض يذكر
   الصور/الوسائط = `SKIP` بسبب موثّق + ملف JSON `{status: skipped}` وخروج 0.

تجاوز البوابة (`--force`) يسجَّل `forced: true`، وفشل الصور حينها يُحسب
`error` لا نجاحاً. جولة تُظهر `skipped` ليست دليل تفوق ولا تخلف —
تُذكر في التقرير كـ **غير قابلة للحكم** (void-round rule: الجولات الباطلة تُوسم).

## الفيكسچرات (اصطناعية، حتمية)

```
vision-bench/
  SKILL.md
  run_vision.py            # المشغّل (argparse، يعيد استخدام shared/backends.py)
  fixtures/
    make_fixtures.py       # المولّد الوحيد الذي يحتاج PIL ( Pillow للصور فقط)
    ui_login.png           # نافذة دخول وهمية 800×600 (زر LOGIN أحمر معروف الصندوق)
    ui_toolbar.png         # شريط أدوات وهمي (زر SAVE أزرق + 3 أزرار)
    arabic_card.png        # بطاقة عربية (3 أسطر، الحقيقة بالترتيب المنطقي)
    grid_count.png         # 7 دوائر زرقاء + 4 مربعات حمراء (مواقع ثابتة)
    ground_truth.json      # الصناديق بمقياس 0-1000 + النصوص + الأعداد + الخط المستخدم
```

أعد التوليد بـ `python3 fixtures/make_fixtures.py` (بلا شبكة، بلا عشوائية).
العربية تُرسم بمحرك RAQM إن وُجد (تشكيل + اتجاه صحيح)، وإلا بمشكّل
احتياطي stdlib (presentation forms مشتقة ذاتياً عبر `unicodedata` —
أي codepoint خاطئ يفشل بصوت عالٍ بدل التوفو الصامت). إن غاب أي خط عربي
من النظام يُوسم `font_used: ...DEGRADED` وتُصبح أحكام V3 **غير مقبولة**
(`arabic_admissible: false`) حتى تُعاد الفيكسچرات بخط عربي حقيقي.

## الاختبارات (برومبتات مجمّدة — PROMPT_PACK vision-v1)

- **V1 تأريض:** `Locate the red LOGIN button … {"x","y","w","h"} 0-1000` —
  النجاح `IoU >= 0.5` (يُقبل أيضاً `x_min/y_min/x_max/y_max`).
- **V2 تأريض:** زر SAVE الأزرق في `ui_toolbar.png` — نفس الحكم.
- **V3 عربي من صورة:** `Read ALL Arabic text …` — النجاح = كل الكلمات
  المفتاحية (`تسجيل`، `الدخول`) حاضرة كسلاسل فرعية (بلا ترتيب) —
  متسامح مع ضجيج OCR، صارم مع الغياب.
- **V4 عدّ:** كم دائرة زرقاء؟ (`7`) — أول عدد صحيح في الرد = الإجابة،
  مطابقة تامة.
- **V5 عدّ أزرار:** كم زراً في الشريط الداكن (دون حقل البحث)؟ (`3`).

القاعدة الإحصائية من الخطة (§0.4): `‎--trials 3` والأغلبية هي الحكم؛
الفجوات < 3pp ضجيج. يُحفظ `iou` الخام دائماً (partial credit على طريقة
OSWorld-2.0 — لا all-or-nothing وحده).

## التشغيل

```bash
# Full suite (env provides BASE_URL/MODEL, or pass flags)
python vision-bench/run_vision.py --backend openai-generic --out results/

# Subset + 3 trials (recommended for verdicts)
python vision-bench/run_vision.py --only V1,V3 --trials 3 --out results/

# List tests without touching any endpoint (offline)
python vision-bench/run_vision.py --list
```

يتوافق مع `shared/run.py` في الأعلام (`--backend/--base-url/--model/--only/--trials/--out`)
ويرسل رسائل OpenAI-style (`content: [{type: text}, {type: image_url, data-URL}]`)
عبر `chat()` من `shared/backends.py` (stdlib + urllib فقط، بلا network
عدا استدعاءات الموديل وفحص `/models` للبوابة).

## التحقق (أمثلة المحكّمات — الإنجليزية مجمّدة)

```python
# V1/V2 grounding (OSWorld-G/ScreenSpot-style)
box = parse_box(reply)   # {x,y,w,h} or {x_min,...} -> [x0,y0,x1,y1]
ok = box is not None and iou(box, GT) >= 0.5   # raw iou always logged
# V3 Arabic-from-image (keyword-substring, order-free)
ok = all(k in reply for k in ("تسجيل", "الدخول"))
# V4/V5 counting (first integer wins, exact match)
m = re.search(r"-?\d+", reply); ok = (m and int(m.group(0)) == 7)
```

## التقارير

نتائج JSON خام في `results/` (لا تعدلها أبداً). التقرير يجب أن يذكر:
نسخة PROMPT_PACK (`vision-v1`)، الـ backend، الموديل، الحرارة (0.2)،
عدد المحاولات، العتاد، `fixture_font`/`fixture_arabic_engine`، متجه
`[V1..V5]` مع `iou` الخام، وأي `status: skipped` مع سببه.
