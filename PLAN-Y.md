# PLAN-Y — الخطة الشاملة للمهام المتبقية (EMO-X)

> العقد الملزم للموجتين + التكامل + QA. كل وكيل يقرأ هذا الملف أولاً
> ثم `SPEC.md` + `DENOMINATORS.md` للأقسام المذكورة في نطاقه.
> القاعدة الحديدية: **ملكية ملفات حصرية** (§3) — أي كتابة خارجها = veto.

## 1. الموجة 1 — 9 وكلاء متوازيين (لا يعتمد بعضهم على بعض)

| الوكيل | المهمة | الملفات المملوكة (كتابة حصرية) | القبول |
|---|---|---|---|
| Y-1 | VOID الرسمي | `shared/schemas.py` (STATUS_CAUSES + classify_cause + VISIBILITY ثوابت)، `shared/manifests.py` (verify_prompt_pack)، `docs/status-model.md`، `tests/harness/test_status_model.py` | جدول الأسباب الـ7 يُختبر؛ العبث بالحزمة يُكتشف |
| Y-2 | Self-test الموسّع | `shared/selftest.py` (جديد: 14 فحصاً + SKIP)، `tests/harness/test_selftest.py` | الثنائيات الغائبة = SKIP لا FAIL؛ العبث = FAIL مغلق |
| Y-3 | Raw immutable تقنياً | `shared/seal.py` (جديد: seal/verify/no-overwrite/derived)، `tests/harness/test_seal.py` | العبث يُكتشف؛ الكتابة فوق RUN_ID مرفوضة |
| Y-4 | Hidden suite | `suites/code-bench-25-hidden/*` (جديد)، `docs/contamination.md`، `tests/backends/test_hidden.py` | instances وقت التشغيل فقط؛ البوابة ترفض بلا opt-in |
| Y-5 | think الرسمي | `shared/backends.py` (إلحاق reasoning_mode_for فقط)، `suites/*/executor.py` سطور الـmode (code25/agent-loop/dynamic)، `tests/harness/test_reasoning_mode.py` | كل attempt يحمل mode صالحاً؛ مقارنة الشروط المختلفة موسومة |
| Y-6 | إحصاء المقارنة | `shared/scoring.py` (reps flag فقط)، `shared/report_v2.py` (compare/render)، `README.md` (حذف 3pp)، `docs/metrics.md`، `tests/scoring/test_compare.py` | 24/25 ضد 23/25 = inconclusive/directional أبداً significant؛ لا كلمة wins |
| Y-7 | Scope-gate الأمني | `shared/safety.py` (تصليب)، `suites/security/executor.py` (جديد)، `security-bench/run_security.py` (بوابة S3-S5)، `docs/security-model.md`، `tests/harness/test_safety_gate.py` | S3-S5 ترفض بلا approval ولا تستدعي الموديل؛ العبث بالـfixtures يُكتشف |
| Y-8 | Manifest مصدر الحقيقة | دمج JSON في `suites/code-bench-25/manifests/*.json` (بيانات فقط) + `tests/backends/test_manifest_truth.py` (تساوي البرومبتات) | 25/25 متساوية بايتاً؛ لا تعديل `.py` |
| Y-9 | Rebuild المتبقي | `docs/REPRODUCIBILITY.md` (قائمة الحقول)، `tests/harness/test_rebuild_manifest.py` | كل حقول القائمة حاضرة في manifest حقيقي |

### العقود العابرة (ينشرها المالك ويستهلكها Y-INT)
- Y-1: `classify_cause(cause)->status` + `VoidRun` + `verify_prompt_pack(name)` + `VISIBILITY/normalize_visibility`.
- Y-2: `run_all_checks()->(ok, rows)` بنفس شكل `run_self_test` (name, bool, detail + "SKIP: ").
- Y-3: `seal_bundle(rundir)->seal.json` + `verify_bundle_seal(rundir)->bool` + `refuse_overwrite`.
- Y-4: اتفاقية `instance_id` + `H3-hidden-*` + حقل `visibility` في manifests.
- Y-5: `reasoning_mode_for(think, num_predict, native)->mode`.
- Y-6: `compare_models/render_comparison` + `paired_bootstrap_diff(..., return_reps=True)`.
- Y-7: `require_scope_gate(family, scope)` + `ScopeDenied` + `verify_fixture_dir`.
- Y-8: manifests تحمل `prompt` النهائي (byte-identical).
- Y-9: قائمة حقول manifest النهائية.

## 2. الموجة 2 — Y-INT (التكامل، يعمل وحده بعد خضرار الموجة 1)

يملك حصرياً: `shared/runner.py` + `shared/run.py` (CLI) + قلب مصدر البرومبت إلى manifests.
Checklist (كلها إلزامية):
1. run_suite: exceptions→VOID (Y-1)، تفويض self-test لـY-2، seal بعد الكتابة (Y-3)، SUITE_DIRS+gates+claim-tier للمخفي (Y-4)، reasoning_conditions (Y-5)، sampling pass-through (موجود — تحقق).
2. run.py: أعلام `--hidden-ok` و`--temperature/--top-p/--top-k/--context` (provider-profile موجود).
3. قلب code25 إلى prompts الـmanifests (Y-8) والحارس هو اختبار التساوي.
4. `tests/run_all.py` أخضر + `--self-test` أخضر + حزمة e2e خام صالحة. ممنوع الانتقال لـQA قبل ذلك.

## 3. المراجعة الشاملة + ضمان الجودة (X-0)

- إعادة تشغيل مستقلة لكل قبول §1 + checklist Y-INT §2.
- فحص المجمّد والملكية والأسرار والشجرة (R1 من `REVIEW-X.md`).
- تقرير `reports/QA_X_final2.md` + حكم GO/NO-GO + punch list مرقّمة.
- ممنوع الدفع قبل GO مكتوبة.

## 5. خطة الاستكمال (completion — تُنفذ بعد GO الموجة 2)

الحالة المُتحقق منها بالفحص المباشر (وليس بالتقارير): تكامل Y-INT
موجود فعلاً في الكود — `run_suite` يحوّل الاستثناءات إلى VOID
(`_void_attempt` + `classify_cause`)، يتحقق من الحزمة المجمّدة، يختم
الحزم (`refuse_overwrite` + `seal_bundle`)، يمرّر `scope` مع رفض المخفي
قبل أي model call، ويسجّل `claim_tier` + `reasoning_conditions`؛
والـCLI يحمل `--hidden-ok` + أعلام الـsampling. التعديلات الأربعة في
SPEC (§14/§27/§28/§B28/§32) موثّقة بلا تنفيذ بعد.

| المرحلة | البنود | التفاصيل |
|---|---|---|
| **C1. إغلاق الموجة 2 (تحقق، لا بناء)** | 1. `tests/run_all.py` + `--self-test` أخضر مؤكد بالتشغيل | أي فشل = إصلاح قبل المتابعة |
| | 2. حزمة e2e مختومة: تشغيل stub واحد + `verify_bundle_seal == ok` ثم حذف الحزمة | الدليل المادي على سلامة التكامل |
| | 3. سلوك البوابات حيّاً: مخفي بلا `--hidden-ok` = REFUSED نظيف؛ security تعمل عبر المسار الجديد | يمنع انحدار Y-4/Y-7 الصامت |
| | 4. تقرير `reports/QA_X_final2.md` + حكم GO/NO-GO | ممنوع الدفع قبل GO مكتوبة |
| **C2. التنظيف قبل العام** | 1. حذف `__pycache__` + `.DS_Store` | الشجرة خام للمستخدمين |
| | 2. ملفات `results/raw/*.json` الحالية **تبقى** (تعمل عليها) — تُستثنى من الـcommit عبر `.gitignore` لا بالحذف | نتائجك الخاصة لا تُدفع للعام |
| | 3. تأكيد `.gitignore` يغطي `results/raw/RUN-*` والحزم التجريبية | |
| **C3. Fine-Tuning (بعد GO فقط، بالترتيب الملزم)** | P0 Scaffold: طبقات L0/L1/L2 في agent-loop + `scaffold_level(s)` + أربعة أرقام Gain + اختبارات ذهبية | SPEC §27 |
| | P1 Hardware: كائن العتاد + `device_class` + فصل Tier A/B + وسم المقارنات المختلطة | SPEC §B28 + §32 |
| | P2 Recovery Precision: صيغة `L/A` الحتمية + زوج (rate, precision) في التقرير + اختبارات القواعد الثلاث | SPEC §14 |
| | P3 Gauntlet: `first_missed` + المرساة المرجعية (الـoracle بايت-مطابق) + اختبارات | SPEC §28 |
| **C4. النشر** | 1. `git add` انتقائي (الكود + المواصفة + الاختبارات فقط) | 2. R2: استنساخ نظيف يعيد إنتاج الأخضر 3. أول baseline حقيقي = R3 قبل أي رقم OFFICIAL |

قاعدة: لا مرحلة تبدأ قبل إغلاق سابقتها بدليل تشغيلي، لا بتقرير.

## 6. خطة الوكلاء لـ C1 (إغلاق الموجة 2 — 3 وكلاء متوازيين)

C1 تحقق لا بناء. الثلاثة يعملون متوازيين بلا اعتماد متبادل.

| الوكيل | المهمة | النطاق المسموح (قراءة/كتابة) | الدليل المطلوب |
|---|---|---|---|
| Z-1 تحقق التكامل | إعادة التشغيل المستقلة: `tests/run_all.py` + `--self-test` + حزمة e2e مختومة واحدة | كتابة: `reports/QA_X_final2.md` فقط (حكم GO/NO-GO)؛ قراءة: كل شيء؛ ممنوع لمس أي كود | `verify_bundle_seal == ok` ثم **حذف الحزمة**؛ أي فشل = punch list مرقّمة لا إصلاح صامت |
| Z-2 تحقق البوابات | سلوك البوابات حيّاً: (1) مخفي بلا `--hidden-ok` = REFUSED نظيف بلا حزمة ولا model call (2) security عبر المسار الجديد مع S3-S5 المرفوضة بلا approval (3) حزمة code25 عادية تنجح وتُختم | كتابة: قسم البوابات داخل `reports/QA_X_final2.md` فقط؛ قراءة: `shared/run*.py` + المنفّذان | ثلاثة أوامر CLI بنتائجها الحرفية في التقرير |
| Z-3 تدقيق الشجرة | R1 كامل: المجمّد (حزمة/قالب/سطر report.py:86/fixtures) + الملكية + مسح الأسرار + الشجرة (لا RUN dirs ولا `__pycache__` ولا `.DS_Store` بعد التنظيف) | كتابة: قسم R1 داخل `reports/QA_X_final2.md` فقط؛ قراءة: كل شيء | جدول PASS/FAIL/OPEN بدليل `file:line` لكل بند |

قاعدة الإغلاق: GO تتطلب Z-1 وZ-2 وZ-3 خضراء معاً في تقرير واحد.
أي NO-GO تُحوَّل لوكيل الإصلاح المالك للملف (Y-1..Y-9 أو Y-INT)، لا
يُصلحها Z بنفسه — الفصل بين المحقق والمنفذ إلزامي.

## 7. خطة الوكلاء لـ C3 (Fine-Tuning — 4 وكلاء متسلسلين)

الترتيب ملزم: P0 ← P1 ← P2 ← P3. لا توازي هنا — كل وكيل يبني على
المنفّذ المدمج لسابقه. القبول من SPEC مباشرة (§14/§27/§28/§B28/§32).

| الوكيل | المهمة | الملفات المملوكة (كتابة حصرية) | القبول |
|---|---|---|---|
| F-0 الطبقات | P0 Scaffold: وضعا L0 (chat فقط) وL1 (read+run فقط) في `episode.py` عبر مفتاح أدوات مسموحة (البرومبتات المجمّدة بايت-مطابقة) + `scaffold_level` في كل attempt + `scaffold_levels` في الـmanifest (عبر `extra=` الموجود) + SG وSG_L1 والنسبيتين في `report_v2` | `suites/agent-loop/episode.py` (إلحاق وضعيات) + `shared/report_v2.py` (قسم SG) + `tests/backends/test_scaffold_tiers.py` | L0/L1/L2 تعمل؛ cross-harness = NON_COMPARABLE؛ ذهبيات الأرقام الأربعة |
| F-1 العتاد | P1 Hardware: كائن `hardware` في `collect_environment` (unknown-tolerant) + `device_class` في الـmanifest + فصل Tier A/B في `report_v2` (رقم EfficiencyScore الحالي = Tier A؛ Tier B معدلات خام + فئة) + وسم المختلط CONDITIONALLY_COMPARABLE | `shared/runner.py` (environment فقط) + `shared/report_v2.py` (قسم الكفاءة) + `tests/harness/test_hardware.py` | M1 ضد i9 موسوم لا مدمج؛ الرقم المدمج مرفوض باختبار |
| F-2 الدقة | P2 Recovery Precision: `recovery_precision()` حتمية في `scoring.py` (القواعد الثلاث + استبعاد التكرار الأعمى + NA للصفر) + زوج (rate, precision) ودليل القراءة في `report_v2` | `shared/scoring.py` (دالة واحدة) + `shared/report_v2.py` (سطرا العرض) + `tests/scoring/test_recovery_precision.py` | الوكيل المتخبط: rate عالٍ + precision منخفض (ذهبية) |
| F-3 التشخيص | P3 Gauntlet: `first_missed` بالترتيب السببي + المرساة المرجعية ( recovery/robustness) في قسم التقرير — **الـoracle بايت-مطابق** (B58 hashes لا تتغير) | `shared/report_v2.py` (قسم gauntlet) + `tests/scoring/test_gauntlet_diag.py` | hashes قبل/بعد متطابقة؛ ذهبيات الترتيب والمرساة |

قواعد مشتركة للـF: stdlib فقط؛ إنجليزية الكود؛ docstring يستشهد بقسم
SPEC؛ المجمّد لا يُمس (برومبتات agent-loop المجمّدة تُعاد كتابتها
بايتاً لا صياغةً)؛ الأخضر الكامل بعد كل وكيل قبل التالي.

## 8. خطة النموذج B — المهارة داخل الوكيل (ليست هدفاً يُختبر، بل واجهة تُستدعى)

الفرق الجوهري عن المحولات (`adapters/` = EMO يختبر وكيلاً خارجياً):
هنا **المستخدم داخل وكيله** (hermes/codex/opencode/pi/forge/…) يستدعي
EMO كمهارة لاختبار نموذج ما. مهارة واحدة محمولة، لا محوّل لكل وكيل.

| الطبقة | الملف | يخدم | المحتوى |
|---|---|---|---|
| B1 المهارة المحمولة | `SKILL.md` (جذر المشروع، صيغة Agent Skills: frontmatter `name/description` + تعليمات + أوامر) | opencode, pi, forge, codex CLI (كلها تقرأ صيغة skill المتوافقة مع Claude وتنفذ shell) | متى تُستدعى المهارة + `python3 <emo-x>/shared/run.py --suite …` حرفياً + قراءة الحزمة الخام + تحذير NON-COMPARABLE عند اختلاف الـharness |
| B2 أمر `/emo` | `commands/emo.md` | codex (`~/.codex/commands/`) + opencode (custom commands) — نفس الملف بلا fork | وسيط رقيق يمرر (`--suite`, `--trials`, `--seed`) لمهارة B1 |
| B3 خادم MCP | `mcp-server/` (stdio + JSON-RPC: أدوات `run_suite`, `self_test`, `health`) | open-web / AnythingLLM (واجهات دردشة بلا shell — الطريقة الوحيدة الممكنة) | **مُنجز**: `mcp-server/server.py` (stdlib فقط، 5 أدوات، نفس البوابات fail-closed) + `tests/backends/test_mcp_server.py` (12 اختباراً) — يخدم أي وكيل MCP-capable |

قواعد ملزمة:
1. المهارة **تستدعي** `shared/run.py` كعملية فرعية — لا تعيد تنفيذ المنطق ولا تنسخ البرومبتات (المجمّد يبقى مصدراً واحداً).
2. كل نتيجة عبر المهارة تحمل `harness` الوكيل المضيف (اسم الوكيل + إصداره) وتُوسم NON-COMPARABLE ضد نتائج `run.py` المباشرة (قاعدة §B58 + درس `ADAPTERS.md` §0).
3. codex CLI يتطلب اشتراك ChatGPT لا مفتاح API — يُوثّق كقيد لا كدعم كامل. cline/kilo (إضافات VS Code بلا CLI) تبقى manual-trace كما في `ADAPTERS.md` §6.
4. لا محوّل جديد لكل وكيل من السبعة — المحولات الثلاثة القائمة عيّنات مرجعية كافية.

الترتيب كان B1 ← B2 ← B3 (المشروط بالطلب) — أُنجزت الثلاث طبقات.
