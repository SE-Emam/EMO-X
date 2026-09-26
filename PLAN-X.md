# EMO-X — خطة التطوير (Master Development Plan)

> **EMO-X = Adaptive Agent Evaluation** — الجيل التكيفي من EMO
> (المنهجية تبقى: Execution • Measurement • Observability).
> المرجع المعياري: `SPEC.md` (Parts A+B) + `DENOMINATORS.md` (Part C, §§C1–C93).
> استراتيجية الإصدارات المرجعية: `SPEC.md` §46.

---

## 0. قاعدة ذهبية

1. لا يُكتب كود جديد قبل تجميد العقد (contract) الذي يعتمد عليه.
2. كل صيغة scoring تُختبر بـ golden test مأخوذ من `SPEC.md` Part B و`DENOMINATORS.md` Part C قبل اعتمادها.
3. `raw → never edited, derived → regeneratable` (§33): أي تصحيح = run جديد، لا تعديل نتائج.
4. العقود المجمّدة لا تُمس: `PROMPT_PACK_v1`، `REPORT_TEMPLATE v1` + `report.py:86`، صيغة `EMO{SYNTH_...}`.

---

## 1. نقطة الانطلاق (Legacy Inventory)

| المكوّن الحالي | الحالة | المصير في EMO-X |
|---|---|---|
| `shared/run.py` (وحيد، ~835 سطر: 25 اختبار + agent loop + CLI) | يعمل (v1) | يُفكك إلى `shared/runner.py` + `suites/` + `generators/` |
| `shared/bench_lib.py`, `backends.py` | يعمل | يُعاد تنظيمه: تنفيذ في `sandbox.py`، اتصال في `backends.py` |
| `shared/report.py` (عقد v1) | مجمّد | يبقى؛ تقرير v2 يُبنى بجانبه لا فوقه |
| `code-bench-25/`, `agent-loop-bench/`, `security-bench/`, `vision-bench/`, `computer-use-bench/`, `adapters/` | SKILLs + fixtures تعمل | تُهاجر إلى `suites/*/` كعيّنات canonical + task manifests (Task DSL §7) |
| `results/*.json` المسطّحة | v1 | تُستبدل بهيكل `results/raw/RUN-ID/` + `results/derived/RUN-ID/` (§33) |
| `SPEC.md`, `DENOMINATORS.md`, `PLAN.md` | موثّقة | `SPEC.md`+`DENOMINATORS.md` = المرجع؛ `PLAN.md` = أرشيف v1 |

---

## 2. البنية المستهدفة (SPEC §41 — مختصرة للتنفيذ)

```text
EMO-X/
├── shared/        # bench_lib, backends, runner, schemas, scoring,
│                  # metrics, manifests, sandbox, safety, adaptive, run
├── prompts/       # PROMPT_PACK_v1 (مجمّد) + PROMPT_PACK_v2 + SHA256SUMS
├── suites/        # code-bench-25, agent-loop, dynamic-code, recovery,
│                  # robustness, security, calibration, long-horizon,
│                  # vision, computer-use  (+ gauntlet في v2.0)
├── generators/    # task_dsl, instance_factory, mutations, seeds
├── judges/        # deterministic, execution, trajectory, llm_judge
├── health/        # saturation, discrimination, flakiness, contamination
├── tests/         # harness, generators, scoring, backends, golden
├── results/       # raw/ + derived/
└── docs/          # architecture, task-dsl, metrics, backend-contract,
                   # security-model, adding-a-suite, benchmark-health
```

خريطة الهجرة (ملزمة):

| من (legacy) | إلى (EMO-X) |
|---|---|
| `shared/run.py:run_code25` + دوال `t*/r*/h*` | `suites/code-bench-25/` manifests + cases (canonical instances) |
| `shared/run.py:run_agent_suite/run_agent` | `suites/agent-loop/` |
| `security-bench/` fixtures + `run_security.py` | `suites/security/` + `judges/` |
| `shared/bench_lib.py` executors | `shared/sandbox.py` + `judges/execution.py` |
| نتائج `results/*.json` | محوّل هجرة لمرة واحدة إلى `results/raw/` (أداة `migrate_v1.py`) |

---

## 3. المراحل (مطابقة §46)

### المرحلة α — الأساس التنفيذي (v2.0-alpha)

| WP | الحزمة | المدخلات | المخرجات (ملفات) | معيار القبول |
|---|---|---|---|---|
| WP1 | العقود والمخططات | SPEC §§32–34, DEN C4,C83 | `shared/schemas.py`, `shared/manifests.py`, `results/raw|derived/` هيكل | مخطط JSON يرفض سجلاً ناقص `trial_id` (اختبار سلبي) |
| WP2 | العزل والـ Self-Test | SPEC §§24,35 | `shared/sandbox.py`, `shared/safety.py`, `--self-test` أخضر | `run.py --self-test` يفشل مغلقاً (fail-closed) عند كسر sandbox |
| WP3 | محرك Scoring + الذهبيات | SPEC Part B, DEN Part C | `shared/scoring.py`, `shared/metrics.py`, `tests/golden/` | كل صيغ B6–B63 وC9–C93 لها golden test؛ `D=0 ⇒ NA` مغطاة (§C82 كاملاً) |
| WP4 | Task DSL + توليد حتمي | SPEC §§7–8 | `generators/*.py`, `prompts/PROMPT_PACK_v2.md` + `SHA256SUMS` | نفس الـseed يُنتج نفس `instance_hash` على جهازين |
| WP5 | هجرة Core-25 | WP1,WP2 | `suites/code-bench-25/` (25 عائلة × canonical) | 25/25 تعمل عبر `--suite code25` + نتائج raw غير قابلة للتحرير |
| WP6 | Failure taxonomy + بصمة | SPEC §30, DEN C25–C27 | `judges/trajectory.py` (أولي) | كل فشل scored يحمل `primary_failure` واحداً (C25) |

**بوابة الخروج من α:** `code25` كاملة على الهيكل الجديد + golden tests خضراء + `run_manifest.json` (§32) لكل run.

### المرحلة β — الوكيل والسلوك (v2.0-beta)

| WP | الحزمة | المخرجات | معيار القبول |
|---|---|---|---|
| WP7 | Recovery + حقن الأعطال (§§13–14) | `suites/recovery/`, `judges/*` recovery | Recovery Rate تُحسب على `D_recoverable` فقط (C29) |
| WP8 | State Drift + Plan Staleness (§§15–16) | `suites/robustness/` (state-drift) | `D_drift=0 ⇒ NA` لا 100% (C58) |
| WP9 | Tool Discipline (§§17–19) | `shared/metrics.py` (TD) | مكوّن غير منطبق = مستبعد من الوسط الهندسي (C41) |
| WP10 | Calibration + Abstention (§§21–22) | `suites/calibration/` | Brier وECE على `D_cal` فقط (C50) |
| WP11 | Benchmark Health (§§11–12, C48–C53,C69–C72) | `health/*.py` + `--health` | `D<5 نماذج ⇒ Discrimination=NA` (C70) |

**بوابة الخروج من β:** `agent-loop` + `recovery` + `calibration` تعمل؛ تقرير يُظهر Capability Profile لا رقماً واحداً (§§55–61).

### المرحلة 2.0 — التكيّف والأفق الطويل

| WP | الحزمة | المخرجات | معيار القبول |
|---|---|---|---|
| WP12 | Adaptive Difficulty (§10) | `shared/adaptive.py` | منحنى قدرة D0–D7 بدل نقطة ثابتة |
| WP13 | Long Horizon (§§25–26) + Time Horizon (B46) | `suites/long-horizon/` | `β≥0 ⇒ time-horizon invalid` (B46) |
| WP14 | Gauntlet (§28) | `suites/gauntlet/` | سيناريو مركّب ≥7 أبعاد متداخلة |
| WP15 | Baseline رسمي 3-trials + تحقق عام | `docs/`, تقرير رسمي | Coverage≥95% + `n≥3` + بوابة السلامة (§B56) |

---

## 4. معايير القبول العامة (تسري على كل WP)

- [ ] stdlib فقط للنواة (لا اعتماديات جديدة دون قرار موثّق).
- [ ] كل دالة scoring: pure + golden test + حالة `D=0 ⇒ NA`.
- [ ] لا رقم يُعرض دون `95% CI` (bootstrap على Task Family ‏— B54) وCoverage وHealth.
- [ ] مقارنة DIRECT فقط عند تطابق `PromptHash+HarnessHash+ManifestHash` (§B58).
- [ ] أي تغيير في (task/oracle/scoring/prompt/harness) = bump نسخة + re-baseline (§45).

---

## 5. المخاطر والتخفيف

| الخطر | التخفيف |
|---|---|
| كسر تجميد v1 أثناء الهجرة | legacy يبقى يعمل حتى بوابة α؛ الهجرة إضافية لا استبدالية |
| Golden tests تُكتب بعد الكود (تزييف الثقة) | العقود والذهبيات تُكتب أولاً (WP1→WP3 قبل WP5) |
| تضارب كتابة بين الوكلاء | ملكية ملفات حصرية لكل وكيل (`AGENTS-X.md` §3) |
| Safety تُعامل كبُعد تعويضي | بوابة `CSVRate=0` إلزامية (§B56) + مراجع المراقب |

---

## 6. سجل التسمية EMO-X (نُفّذ)

- `EMO-Benchmark-Skills` / `EMO Benchmark Skills` / `emo-bench` ← `EMO-X` / `emo-x` في: README, INSTALL, LICENSE, PLAN, SPEC (العنوان + شجرة §41), DENOMINATORS (العنوان + النسب), `shared/*.py` (docstrings)، `hermes_adapter.py`، SKILLs العربية الثلاثة.
- **مجمّد عمداً (لم يُمس):** `PROMPT_PACK_v1.md`، `REPORT_TEMPLATE.md`، سطر الإخراج `report.py:86`، معرّفات الصيغ (`EMO_…`)، `EMO-Core-25`، `EMO Gauntlet`، `EMO{SYNTH_…}`، `EMO trace JSON`.
- خطوة خارجية متبقية: إعادة تسمية المستودع على GitHub + مجلد العمل (تتطلب git/GitHub — لم تُنفّذ هنا).
