# EMO-X — خطة المراجعة (Review Plan)

> تكمّل `PLAN-X.md` (بناء) و`AGENTS-X.md` (تنفيذ): هذه الخطة تحكم **التحقق**
> قبل الدفع، بعده، ودورياً. المرجع المعياري: `SPEC.md` + `DENOMINATORS.md`.
> المنفّذ: دور المراقب X-0 (بشري أو وكيل) — تقاريره في `reports/QA_X_*.md`.

---

## 1. أنواع المراجعة

| # | المراجعة | متى | الهدف | المخرج |
|---|---|---|---|---|
| R1 | ما قبل الدفع (Pre-push) | قبل كل `git push` | لا كسر عقد، لا أسرار، الاختبارات خضراء | `reports/QA_X_prepush_<date>.md` + GO/NO-GO |
| R2 | ما بعد الدفع (Post-push/CI) | بعد كل دمج لـ`main` | الاستنساخ من الصفر يعمل (`clone → self-test → run_all`) | CI أخضر أو تذكرة إصلاح |
| R3 | مراجعة إصدار رسمي (Baseline) | قبل أي ادعاء OFFICIAL | شروط §B59 كاملة (n≥3، تجميد، seeds، manifests، coverage≥95%) | `reports/QA_X_baseline_<model>.md` |
| R4 | مراجعة دورية للبنشمارك نفسه | شهرياً أو كل 5 نماذج | صحة البنشمارك: تشبع/تمييز/تذبذب/تلوث (§§11–12، C48–C53) | `reports/QA_X_health_<date>.md` + قرارات إيقاف/تدوير مهام |

---

## 2. قائمة R1 — ما قبل الدفع (بوابة إلزامية)

- [ ] `python3 tests/run_all.py` → PASS كل الحزم (حالياً 5/5 = 214).
- [ ] `python3 shared/run.py --self-test` → PASS (حالياً 10/10، fail-closed).
- [ ] المجمّد سليم: `PROMPT_PACK_v1` header، `REPORT_TEMPLATE` (8 أقسام بالترتيب)، `report.py:17 + :86`، fixtures الـ7 مطابقة sha256 للأصل، منطق `run/bench_lib/backends` الإرثي بلا تعديل (إضافات CLI فقط).
- [ ] لا أسرار: `rg -i "api[_-]?key|token|secret|password" --glob '!reports/*'` نظيف، و`.env` غير متتبّع (`.gitignore`).
- [ ] الملكية: ملفات جديدة داخل مجلدات مالكيها فقط (`AGENTS-X.md` §3).
- [ ] أي تغيير في (task/oracle/scoring/prompt/harness) ← bump نسخة + re-baseline (§45) وإلا NO-GO.
- [ ] `git status` نظيف من ملفات مؤقتة (`__pycache__/`, `results/raw/RUN-*/` التجريبية تُحذف أو تُستثنى عمداً).

**النتيجة:** GO (ادفع) أو NO-GO (قائمة إصلاح مرقّمة تمنع الدفع).

---

## 3. قائمة R2 — ما بعد الدفع (استنساخ نظيف)

```bash
git clone <URL> emo-x && cd emo-x
python3 shared/run.py --self-test        # يجب: PASS
python3 tests/run_all.py                 # يجب: PASS كل الحزم
python3 shared/run.py --suite code25 --trials 1 --out /tmp/e2e/
ls /tmp/e2e/RUN-*/  # manifest.json + events.jsonl + responses.jsonl + environment.json
```

أي فشل هنا = تذكرة P0 (البيئة المكسورة تُبطل أي نتيجة لاحقة — §B58).

---

## 4. قائمة R3 — مراجعة Baseline رسمي (قبل نشر أي رقم)

- [ ] `n ≥ 3` trials لكل مهمة + seeds مسجّلة + معرّف موديل + إصدارات runtime.
- [ ] تجميد ثلاثي متطابق: `PromptHash + HarnessHash + TaskManifestHash` (§B58) — وإلا تُوسم المقارنة NON-COMPARABLE.
- [ ] `Coverage ≥ 0.95` (§B59) وإلا PILOT لا OFFICIAL.
- [ ] بوابة السلامة: `CSVRate = 0` وإلا NOT RANKABLE (§B56) — تُعرض المقاييس ويُحجب الرقم الموحّد.
- [ ] التقرير العامي الكامل (§B60): Pass Rate، Partial، Generalization، Tool Discipline، Recovery، Efficiency، Calibration، Safety، Long-Horizon، Human-Minutes، Failure Fingerprint، ‏95% CI (bootstrap عائلي B54)، Coverage، Health — **ممنوع عرض رقم واحد فقط** (§B61).
- [ ] النتائج `raw/` محفوظة غير معدّلة والمشتقات قابلة لإعادة التوليد (§33).

---

## 5. قائمة R4 — صحة البنشمارك نفسه (مكافحة الشيخوخة)

| المقياس | العتبة | الإجراء عند التجاوز |
|---|---|---|
| Saturation (§11، C49/C71) | `p̄ > 0.95` عبر ≥3 نماذج | المهمة تاريخية؛ تُفعَّل عائلة بديلة |
| Discrimination (C50/C70) | `D ≈ 0` أو NA دائم | تُراجع الصياغة أو تُستبعد من الوزن |
| Flakiness (C48/C69) | `4p(1-p) > 0.25` | تُجمّد المهمة حتى يُصلح المصدر |
| Contamination proxy (B13) | `NoveltyGap` موجب كبير ومستمر | تُدوَّر instances جديدة (seed جديد) |
| Judge reliability (C52) | `< 0.90` | LOW-CONFIDENCE؛ لا يُستخدم كعنوان وحيد |
| Health الإجمالي (C72) | `< 0.80` | التشغيل NOT RANKABLE حتى التعافي (§B56) |

---

## 6. صلاحيات المراقب (Veto فوري — من `AGENTS-X.md` §5)

1. كتابة خارج الملكية أو تعديل عقد مجمّد.
2. صيغة scoring بلا golden test أو بلا تغطية `D=0 ⇒ NA`.
3. دمج `ERROR/VOID` في مقام أداء، أو double-counting داخل محور واحد.
4. رقم بلا CI/Coverage/Health.
5. تخمين عند الغموض بدل `INSUFFICIENT_EVIDENCE` (DEN §C88).

---

## 7. قالب التقرير (إلزامي لكل R)

`reports/QA_X_<type>_<date>.md`: النطاق → الفحوص (أمر + نتيجة) → جدول الأحكام (PASS/FAIL/OPEN بدليل `file:line`) → الحكم GO/NO-GO → قائمة الإصلاح المرقّمة → بنود INSUFFICIENT_EVIDENCE.

---

## 8. الجدول التشغيلي المقترح الآن

1. **اليوم:** R1 على الحالة الحالية (كل WP مغلقة — يُعاد تأكيد GO الدفع).
2. **يوم الدفع:** R2 بعد أول push (استنساخ نظيف).
3. **أول baseline حقيقي:** R3 قبل نشر أي رقم OFFICIAL.
4. **ثم:** R4 شهرياً.
