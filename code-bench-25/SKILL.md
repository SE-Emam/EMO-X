---
name: code-bench-25
description: حزمة اختبارات الكود الـ25 (T/R/H) — تنفيذ حقيقي لكل إجابة مع بوابات صارمة موثقة. استخدمها لمقارنة أي موديل قبل اعتماده.
---

# اختبار الكود 25 (code-bench-25)

## ما هذا؟

25 اختباراً تنفذ إجابة الموديل فعلياً (compilers و interpreters حقيقية)، لا بالنظر.
كل اختبار: برومبت مجمّد من `shared/PROMPT_PACK_v1.md` + تحقق تنفيذي + نتيجة JSON خام.

## محتويات الحزمة (25 اختباراً)

- **T (أساسي + عربي):** ‏T2 فيبوناتشي، T3 إصلاح `is_even`، T4 مجموع JS، T5 شرح عربي، T6 كود عربي، T7 التزام JSON، T8 مهمة ملف.
- **R (واقعي):** ‏R1 برنامج Rust كامل، R2 استعلام SQLite، R3 أوامر git،
  ‏R4 ملف vercel.json، R5 دالة supabase-js، R6 يونيفايد diff،
  ‏R7 استدعاء أداة بصيغة صارمة، R8 رسالة commit، R9 صفحة HTML/CSS،
  ‏R10 مكون React، R11 تحقق TypeScript، R12 استعلام Postgres.
- **H (صعب):** ‏H1 أرقام متزايدة، H2 معادلة دايوفانتية، H3 باقي القسمة،
  ‏H4 أطول palindrome، H5 دلو الرموز، H6 أول occurrence.

ملاحظة: الترقيم يبدأ من T2 (سبعة اختبارات T + اثنا عشر R + ستة H = 25).

## ملاحظات المنهجية (لا تغيرها دون نسخة PROMPT_PACK جديدة)

1. **صرامة بوابة T5:** النجاح يتطلب `arabic_ratio > 0.3` — الردود المختلطة
   (عربي قصير + إنجليزي طويل) تفشل عمداً. هذا يقيس الشرح العربي الحقيقي.
2. **فحص R6 المصحح:** لا يكفي أن يطبق الـ diff؛ يجب أن يحتوي الملف الناتج
   `def sum_all` **و** جسم الدالة الأصلي (`s += i`). diff يطبق لكنه خاطئ = فشل.
3. **فحص R10 المصحح:** مطابقة غير حساسة لحالة الأحرف لـ `useState(0)` بدون مسافات،
   مع `onClick` و `setCount` واسم `Counter` و `export`. يمنع الإيجابيات الكاذبة.
4. **فحص R12 المصحح:** الصفوف المتوقعة `["Keyboard", "Mouse"]` فقط
   (أرخص من 100 مرتبة تنازلياً: 50 ثم 25) — أي ترتيب آخر = فشل.
5. **قاعدة التشغيل الثلاثي H3:** بعد ملاحظة عدم استقرار H3، الجولات الأحادية له
   **غير مقبولة**. شغّل `--trials 3` واعتمد الأغلبية/المتوسط.
6. **`think:false` للرياضيات:** اختبارات H1–H3 تعمل عبر الـ native endpoint مع
   `think=false` (و `num_predict=1400` لـ H2). التفكير المطول يضيف ضجيجاً
   ويكسر استخراج الإجابة الرقمية.

## التشغيل

```bash
# Full suite against a Kaggle tunnel
python shared/run.py --backend kaggle --base-url "$BASE_URL" \
    --model "$MODEL" --suite code25 --out results/

# Subset + 3 trials (required for H3 verdicts)
python shared/run.py --suite code25 --only T5,R7,H3 --trials 3 --out results/

# Commercial / local OpenAI-compatible endpoint
python shared/run.py --backend openai-generic --suite code25 --out results/
```

## التحقق

```python
# Every answer executes in a real toolchain (bench_lib verifiers):
ok, log = run_py(code, "assert fib(0)==0 and fib(10)==55; print('FIB_OK')")
ok, log = run_js(code, "if (sumArr([1,2,3,4])!==10) throw 1; console.log('JS_OK')")
ok, log = run_rust(code)          # rustc -O, program must print PRIME_OK
ok, log = verify_tsc(code)        # tsc --noEmit --strict (+ static fallback)
ok, log = verify_patch("calc.py", orig, diff, must_contain=("def sum_all", "s += i"))
```

## التقارير

نتائج JSON خام في `results/` (لا تعدلها أبداً) + ملخص `pass/total`.
التقرير يجب أن يذكر: نسخة PROMPT_PACK، الـ backend، الحرارة، عدد المحاولات، العتاد.
