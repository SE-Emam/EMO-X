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

```bash
EMOX=/path/to/emo-x   # جذر هذا المستودع

# 0) تحقق أولاً (دقيقتان، بلا endpoint) — أي فشل يوقف كل شيء:
python3 $EMOX/shared/run.py --self-test
python3 $EMOX/tests/run_all.py

# 1) جناح الكود (ابدأ هنا دائماً):
python3 $EMOX/shared/run.py --backend openai-generic --suite code25 --out results/

# 2) الملف الكامل (بعد نجاح 1):
python3 $EMOX/shared/run.py --suite profile --trials 3 --out results/

# 3) أجنحة مركزة:
python3 $EMOX/shared/run.py --suite dynamic-code --instances 20 --seed 12345
python3 $EMOX/shared/run.py --suite recovery --fault-rate 0.25
python3 $EMOX/shared/run.py --suite gauntlet
python3 $EMOX/shared/run.py --suite code25 --only T5,R7,H3 --trials 3

# 4) صحة البنشمارك نفسه:
python3 $EMOX/shared/run.py --health

# 5) تقرير العميل (القالب المجمّد + ختم QA):
python3 $EMOX/shared/run.py --report results/<model>_<stamp>.json --model MODEL-ID
```

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
| opencode | أوامر مخصصة + MCP (لا SKILL.md أصيلاً) | انسخ `commands/emo.md` لمجلد custom-commands، أو اربط خادم MCP: `opencode mcp` — انظر `mcp-server/` |
| pi | `--skill <path>` أصيل (يُحمَّل ملفاً أو مجلداً، قابل للتكرار) | `pi --skill /path/to/emo-x/SKILL.md "benchmark this model"` — يُحمَّل مباشرة بلا تثبيت |
| hermes-agent | مهارات أصيلة `SKILL.md` (frontmatter `name/description/version/category`) — محلية `./.hermes/skills/` + `skills trust`، أو `~/.hermes/skills/`، أو `publish`/`sync` | **مثبتة في هذا المستودع**: `.hermes/skills/emo-x/SKILL.md` — نفّذ `hermes skills trust` في الجذر ثم تُحمَّل تلقائياً |
| forge-agent (DeepSeek/Gemini) | **plugins بلغة JS** (`~/.deepseek-agent/tools/*.js`) — لا SKILL.md | انسخ `adapters/forge_agent_emo_x.js` إلى `~/.deepseek-agent/tools/emo_x.js` (مثبت ومُتحقق: `forge-agent --list-plugins` تُظهر `emo_x`) |
| codex CLI | `~/.codex/commands/` + shell | انسخ `commands/emo.md` إلى `~/.codex/commands/emo.md` ثم `/emo code25` |
| kilo / cline | إضافتا VS Code **بلا CLI** — لا تحميل آلي ممكن | manual-trace: نفّذ الأوامر يدوياً من `SKILL.md` وسجّل النتائج بنفس الحقول |

قيد hermes الخاص: أوامر `run.py` تُنفَّذ عبر أدوات الـterminal لدى
hermes (`--yolo` للتشغيل غير التفاعلي)؛ سجِّل `cli_command_argv`
وإصدار hermes (`hermes --version`) ضمن `harness` كل نتيجة — نفس قاعدة
NON-COMPARABLE أعلاه.
