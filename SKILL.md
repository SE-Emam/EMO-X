---
name: emo-x
description: Adaptive, execution-based evaluation of AI coding models and agents (EMO-X). Use when the user asks to benchmark a model, run a capability profile, verify harness health, or compare two models with uncertainty. Invokes shared/run.py as a subprocess and reads the immutable raw bundle.
version: 2.0.0
category: qa
---

# EMO-X Skill (Model B: skill inside the agent)

## ما هذه المهارة؟

EMO-X يقيس ما **يُنجَز تنفيذياً** لا ما يُقال نصّياً: أجنحة كود وتنفيذ
حقيقي، حلقات وكيلية، تعافٍ، معايرة، سلامة، وأفق طويل — مع بصمة فشل
وشك إحصائي، لا رقماً واحداً.

## متى تُستدعى؟

- المستخدم يطلب تقييم/مقارنة نموذج (`benchmark this model`, `قارن النموذجين`).
- المستخدم يطلب تقرير قدرات (`capability profile`, `تقرير EMO`).
- المستخدم يشتبه بكسر في البيئة (`self-test`, `تحقق من الـharness`).

## القاعدة الحديدية

هذه المهارة **تستدعي** `shared/run.py` كعملية فرعية — لا تعيد تنفيذ
المنطق، لا تنسخ البرومبتات، لا تخترع أرقاماً. النتائج تُقرأ من الحزمة
الخام فقط (`results/raw/RUN-ID/`). أي رقم بلا حزمة خام = غير مقبول.

## التشغيل (نفّذ حرفياً، عدّل المسار فقط)

> **التقارير تُكتب في مجلد عمل الوكيل** (cwd)، لا في جذر المهارة:
> مرّر `--out` دائماً (مجلد المشروع الحالي)، واعرض التقرير بالمتصفح
> عبر `report.html` المولّد بجانب الحزمة (انظر "التقرير البياني" أدناه).

```bash
EMOX=/path/to/emo-x   # جذر هذا المستودع
OUT=.                  # مجلد المشروع الذي يعمل به الوكيل (cwd) — لا تغيّره لجذر المهارة

# 0) تحقق أولاً (دقيقتان، بلا endpoint) — أي فشل يوقف كل شيء:
python3 $EMOX/shared/run.py --self-test
python3 $EMOX/tests/run_all.py

# 1) جناح الكود (ابدأ هنا دائماً):
python3 $EMOX/shared/run.py --backend openai-generic --suite code25 --out $OUT/results/

# 2) الملف الكامل (بعد نجاح 1):
python3 $EMOX/shared/run.py --suite profile --trials 3 --out $OUT/results/

# 3) أجنحة مركزة:
python3 $EMOX/shared/run.py --suite dynamic-code --instances 20 --seed 12345 --out $OUT/results/
python3 $EMOX/shared/run.py --suite recovery --fault-rate 0.25 --out $OUT/results/
python3 $EMOX/shared/run.py --suite gauntlet --out $OUT/results/
python3 $EMOX/shared/run.py --suite code25 --only T5,R7,H3 --trials 3 --out $OUT/results/

# 4) صحة البنشمارك نفسه:
python3 $EMOX/shared/run.py --health

# 5) تقرير العميل (القالب المجمّد + ختم QA) — يُكتب في $OUT/reports/:
python3 $EMOX/shared/run.py --report $OUT/results/<model>_<stamp>.json --model MODEL-ID --out $OUT/reports/
```

## سير العمل: Manual أم Auto (اسأل المستخدم أولاً)

عند طلب benchmark لنموذج، **خيّر المستخدم صراحة** بين أمرين قبل أي تنفيذ:

| | Manual workflow | Auto workflow |
|---|---|---|
| المعنى | الوكيل ينفذ خطوة → يعرض النتيجة → **ينتظر تأكيدك** قبل التالية | الوكيل يتولى المهمة كاملة (self-test ← code25 ← profile ← تقرير بياني) **دون الرجوع إليك** حتى يكتمل ويظهر التقرير |
| متى | endpoint جديد، أول تجربة، نتائج حساسة | endpoint معروف يعمل، تشغيل روتيني |
| الإيقاف | أي فشل يوقف ويطلب القرار | الفشل الحرج فقط (self-test أحمر، VOID شامل) يوقف؛ الباقي يُسجَّل ويُتابَع |

سؤال التخيير الحرفي: *"benchmark لِـ MODEL-ID: تريد Manual (خطوة بخطوة مع تأكيدك) أم Auto (أكمل كل شيء وأعرض التقرير)؟"*

قواعد Auto الإلزامية: self-test أخضر أولاً وإلا توقف فوري؛ الترتيب code25 ← profile ← تقرير؛ لا S3–S5 ولا hidden بلا موافقة صريحة مسبقة؛ التقرير البياني يُفتح تلقائياً في النهاية؛ أي VOID شامل يُعلن ولا يُتجاوز بصمت.

## التقرير البياني (HTML + رسوم — يُفتح بالمتصفح)

بعد أي تشغيل، ولّد العرض من الحزمة الخام وافتحه:

```bash
python3 $EMOX/shared/render_report.py $OUT/results/raw/RUN-ID/ --out $OUT/reports/RUN-ID/
open $OUT/reports/RUN-ID/report.html   # macOS; أو xdg-open على Linux
```

**عدة نماذج (leaderboard):** نموذج واحد أو N — حسب ما يريد المستخدم:

```bash
python3 $EMOX/shared/render_leaderboard.py $OUT/results/raw/RUN-A/ [$OUT/results/raw/RUN-B/ ...] --out $OUT/reports/board/
open $OUT/reports/board/leaderboard.html
```

اللوحة تحوي: جدول مرتبة بنطاقات (bands — الفترات المتداخلة تتشارك
المرتبة، لا دقة زائفة) + جراف SVG (أشرطة + شوارب CI) + جدول المقارنات
الزوجية (`significant/directional/inconclusive` — كلمة "فائز" ممنوعة).

**لوحة security (بيانات v1 المسطحة):**

```bash
python3 $EMOX/shared/render_security_board.py $OUT/results/raw/security_*.json --out $OUT/reports/security-board/
open $OUT/reports/security-board/security-board.html
```

جدول مرتبة + مصفوفة خضراء/حمراء لكل اختبار (S1–S5) + tokens/secs +
حالة الـscope — نموذج واحد أو N.

العرض يحوي: شريط القدرات (Capability Profile bars) + بصمة الفشل
(fingerprint bars) + الكفاءة Tier A/B + فترة الشك 95% CI + جدول
`claim_tier`/`reasoning_conditions`/البوابات — من الحزمة الخام فقط،
بلا إنترنت وبلا اعتماديات (SVG/CSS مضمّن).

المفاتيح عبر البيئة لا الأعلام:

```bash
export OPENAI_BASE_URL="https://HOST/v1" OPENAI_API_KEY="$KEY" OPENAI_MODEL="MODEL-ID"
```

## قراءة النتيجة

- الحزمة: `results/raw/RUN-ID/{manifest,events,responses,environment}.json*` — لا تُعدَّل أبداً.
- اعرض: Capability Profile + بصمة الفشل + الكفاءة + الشك (95% CI) — **ممنوع اختزالها لرقم واحد** (SPEC §B61).
- المقارنة بين نموذجين: `compare_models` في `shared/report_v2.py` فقط — الحالات المسموحة `significant / directional / inconclusive`، وكلمة "فائز" ممنوعة.

## تحذير المقارنة (إلزامي في كل تقرير)

سجّل harness الوكيل المضيف (اسمه + إصداره) بجانب كل نتيجة موسومة
بهذه المهارة. أي مقارنة ضد نتائج `run.py` المباشرة موسومة
**NON-COMPARABLE** (harness+model هي الوحدة — SPEC §B58، `adapters/ADAPTERS.md` §0).

## ما لا تفعله هذه المهارة

- أجنحة السلامة S3–S5 تحتاج موافقة scope (`EMOX_SCOPE_APPROVED=1` + `EMOX_SCOPE_TARGET=synthetic:…`) — بلا موافقة تُرفض fail-closed، لا تتجاوزها.
- الجناح المخفي (`code25-hidden`) يحتاج `--hidden-ok` — لا تستخدمه للمطالبات العامة.
- `vision` يحتاج endpoint متعدد الوسائط؛ `computer-use` تجريبي (PILOT).

## التثبيت حسب الوكيل (opencode / pi / forge-agent / codex / hermes-agent)

> تنبيه: **لا يوجد شيء اسمه forgecode** — الاسم الصحيح **forge-agent**
> (أمر `forge-agent`/`fa`)، وآليته plugins بلغة JS في
> `~/.deepseek-agent/tools/` — لا يقرأ SKILL.md.

| الوكيل | آلية المهارة | التثبيت |
|---|---|---|
| opencode | أوامر مخصصة + MCP (لا SKILL.md أصيلاً) | انسخ `commands/emo.md` لمجلد custom-commands، أو اربط خادم MCP: `opencode mcp add emo-x -- python3 /path/to/emo-x/mcp-server/server.py` — انظر `mcp-server/` |
| pi | `--skill <path>` أصيل (يُحمَّل ملفاً أو مجلداً، قابل للتكرار) | `pi --skill /path/to/emo-x/SKILL.md "benchmark this model"` — يُحمَّل مباشرة بلا تثبيت |
| hermes-agent | مهارات أصيلة `SKILL.md` (frontmatter `name/description/version/category`) — محلية `./.hermes/skills/` + `skills trust`، أو `~/.hermes/skills/`، أو `publish`/`sync` | **مثبتة في هذا المستودع**: `.hermes/skills/emo-x/SKILL.md` — نفّذ `hermes skills trust` في الجذر ثم تُحمَّل تلقائياً |
| forge-agent (DeepSeek/Gemini) | **plugins بلغة JS** (`~/.deepseek-agent/tools/*.js`) — لا SKILL.md | انسخ `adapters/forge_agent_emo_x.js` إلى `~/.deepseek-agent/tools/emo_x.js` (مثبت ومُتحقق: `forge-agent --list-plugins` تُظهر `emo_x`) |
| codex CLI | `~/.codex/commands/` + shell | انسخ `commands/emo.md` إلى `~/.codex/commands/emo.md` ثم `/emo code25` |
| kilo / cline | إضافتا VS Code **بلا CLI** — لا تحميل آلي ممكن | manual-trace: نفّذ الأوامر يدوياً من `SKILL.md` وسجّل النتائج بنفس الحقول |

قيد hermes الخاص: أوامر `run.py` تُنفَّذ عبر أدوات الـterminal لدى
hermes (`--yolo` للتشغيل غير التفاعلي)؛ سجِّل `cli_command_argv`
وإصدار hermes (`hermes --version`) ضمن `harness` كل نتيجة — نفس قاعدة
NON-COMPARABLE أعلاه.
