# EMO-X — خطة الوكلاء التنفيذيين (Execution Agents Plan)

> يعمل الوكلاء بالتوازي عبر `Task` tool. كل وكيل مالك حصري لملفاته (§3).
> المراقب `X-0` يعمل باستمرار ويملك حق النقض (veto) عند كسر العقود.

---

## 1. التشكيلة

| الوكيل | الدور | المرحلة | حزم العمل |
|---|---|---|---|
| **X-0 Monitor** | مراقبة ومتابعة + QA + منع التضارب | مستمر (α→2.0) | كل WP (قراءة فقط + veto) |
| **X-1 Contracts** | العقود: schemas, manifests, هيكل results, self-test, sandbox | α أولاً (يفتح الطريق) | WP1, WP2 |
| **X-2 Generators** | Task DSL + توليد حتمي + طفرات + PROMPT_PACK_v2 | α (بعد WP1) | WP4 |
| **X-3 Scoring** | محرك scoring + metrics + golden tests (Parts B+C) | α (بعد WP1) | WP3, WP6 |
| **X-4 Suites** | هجرة Core-25 + agent-loop + security إلى `suites/` | α→β (بعد WP1,WP2) | WP5 (+β: WP7–WP10 suites) |
| **X-5 Integration** | health + adaptive + CLI + تقرير v2 + long-horizon + gauntlet | β→2.0 (بعد WP3) | WP11–WP15 |

---

## 2. مخطط التوازي (DAG)

```text
Batch 0 (فوري، متوازٍ):  X-1 يبدأ العقود
                          X-0 يبدأ المراقبة (baseline: self-test v1 أخضر؟)
Batch 1 (بعد تجميد schemas/manifests):
                          X-2  ┐
                          X-3  ├─ متوازٍ تماماً (ملفات منفصلة)
                          X-4  ┘  (X-4 يحتاج WP2 أيضاً للتنفيذ)
Batch 2 (بعد WP3 أخضر):  X-5 health/adaptive/CLI
Batch 3 (2.0):            X-5 gauntlet/long-horizon + X-4 suites المتبقية
```

القاعدة: لا وكيل ينتظر وكيلاً آخر داخل نفس الـBatch — الاعتماد فقط على العقود المجمّدة من Batch 0.

---

## 3. ملكية الملفات (حصرية — ممنوع الكتابة خارجها)

| الوكيل | يملك كتابةً | يقرأ فقط |
|---|---|---|
| X-1 | `shared/schemas.py`, `shared/manifests.py`, `shared/sandbox.py`, `shared/safety.py`, `results/` هيكل, `tests/harness/` | SPEC Parts A |
| X-2 | `generators/*`, `prompts/PROMPT_PACK_v2.md`, `prompts/SHA256SUMS`, `tests/generators/` | `shared/schemas.py` |
| X-3 | `shared/scoring.py`, `shared/metrics.py`, `judges/*`, `tests/scoring/`, `tests/golden/` | DENOMINATORS §§C1–C93 |
| X-4 | `suites/*`, `tests/backends/` (هجرة) | `shared/sandbox.py`, `shared/schemas.py` |
| X-5 | `health/*`, `shared/adaptive.py`, `shared/runner.py`, `shared/run.py` (CLI), `docs/*`, تقرير v2 | كل ما سبق (قراءة) |
| X-0 | لا يكتب كوداً؛ يكتب `reports/QA_X*.md` فقط | كل شيء |

---

## 4. بروتوكول التسليم بين الوكلاء

1. X-1 ينشر **العقود المجمّدة**: `schemas.py` (حقول §C83 + `run_manifest.json` §32) + `manifests.py` (Task DSL §7). أي تغيير لاحق = bump نسخة.
2. X-3 ينشر **سجل المقامات** كوحدة قابلة للاستيراد (§C81) + جدول الحالات الحدّية (§C82) كاختبارات — على X-4/X-5 استيراده لا إعادة اختراعه.
3. X-2 ينشر **مفتاح الحتمية**: `seed → instance_hash` (`generators/seeds.py`) — على X-4 استخدامه لكل instance جديد.
4. التسليم = ملفات + اختبارات خضراء + سطر في `PLAN-X.md` §4 checklist. بلا ذلك يُرفض الاستلام (X-0).

---

## 5. صلاحيات المراقب X-0 (نقض فوري عند)

- كتابة خارج الملكية (§3) أو تعديل عقد مجمّد (PROMPT_PACK_v1, REPORT v1, `EMO{SYNTH_…}`).
- صيغة scoring بلا golden test أو بلا تغطية `D=0 ⇒ NA`.
- دمج `ERROR/VOID` في مقام أداء (§C9) أو double-counting داخل محور واحد (§C77).
- عرض رقم بلا CI/Coverage/Health (§B60).

تقرير المراقب: `reports/QA_X_<date>.md` (مخالفات + حالة كل WP + اختناقات).

---

## 6. مهام جاهزة للإطلاق (تُلصق في Task tool)

### X-0 — Monitor (يُطلق أولاً، يعمل طوال المشروع)

```text
Role: EMO-X QA monitor (read-only over code, write-only reports/QA_X_*.md).
Loop: (1) verify PLAN-X.md §4 checklist per WP, (2) grep for contract breaks
(frozen: PROMPT_PACK_v1, REPORT_TEMPLATE v1, EMO{SYNTH_), (3) run
python shared/run.py --self-test + pytest tests/ when present,
(4) report violations with file:line. You own no product files and change none.
Stop rule: report INSUFFICIENT_EVIDENCE rather than guessing (DEN §C88).
```

### X-1 — Contracts & Sandbox (Batch 0)

```text
Build per SPEC §§32-35 + DEN §§C4,C83: shared/schemas.py (attempt/instance/
manifest/run_manifest JSON schemas with negative tests), shared/manifests.py
(Task DSL §7 manifest loader+validator), shared/sandbox.py + shared/safety.py
(sandbox_only, forbidden paths, fail-closed), results/raw|derived/ layout (§33).
Write tests/harness/. Frozen touch ban: PROMPT_PACK_v1, REPORT_TEMPLATE,
report.py output line. Done = --self-test green + schemas reject bad logs.
```

### X-2 — Generators (Batch 1, needs X-1 schemas)

```text
Build per SPEC §§7-8: generators/task_dsl.py, instance_factory.py, mutations.py,
seeds.py (deterministic seed→instance + instance_hash/oracle_hash), canonical→
novel variant classes (§9), prompts/PROMPT_PACK_v2.md + SHA256SUMS. Golden rule:
same seed on two machines → identical hashes. Write tests/generators/.
Never embed expected answers in generators (§6).
```

### X-3 — Scoring Engine (Batch 1, needs X-1 schemas)

```text
Implement shared/scoring.py + shared/metrics.py + judges/ per SPEC Part B
(B4-B63) and DEN Part C (C9-C93) EXACTLY. Import-first: build the denominator
registry (C81) as importable code. Every formula gets a golden test in
tests/golden/ incl. full edge table C82 with D=0⇒NA (never 0). Aggregation
order: Attempt→Instance→Variant→Task→Capability (C78). Primary labels mutually
exclusive; secondary tags may overlap (C25-C26). Done = all goldens green.
```

### X-4 — Suites Migration (Batch 1, needs X-1 + X-2 inout)

```text
Migrate legacy suites to suites/ as canonical task families with Task DSL
manifests: code-bench-25 (25 families from shared/run.py t*/r*/h*), agent-loop
(run_agent episode), security (fixtures incl. EMO{SYNTH_} UNCHANGED), vision,
computer-use. Use X-2 seeds for instance ids, X-1 schemas for outputs, X-3
registry for scores — reimplement nothing. Keep legacy files runnable until
α-gate. Done = --suite code25 green on new layout with raw/ manifests (§32).
```

### X-5 — Health/Adaptive/CLI/Report (Batch 2, needs X-3 green)

```text
Build health/ (saturation/discrimination/flakiness/contamination per C48-C53,
C69-C72), shared/adaptive.py (D0-D7 controller §10), new CLI flags per SPEC
§42 (--suite dynamic-code/recovery/gauntlet/profile, --self-test, --health),
docs/*.md, and the v2 capability-profile report (§§43-44, B60-B61: profile+
fingerprint+efficiency+uncertainty, never one number). Safety gate CSVRate=0
(B56) enforced. Done = --health + full profile run with CI+coverage+health.
```

---

## 7. تسلسل الإطلاق المقترح الآن

1. أطلق **X-0** أولاً (يؤسس خط الأساس).
2. أطلق **X-1** (Batch 0).
3. عند تجميد العقود: أطلق **X-2 + X-3 + X-4** متوازية.
4. عند اخضرار WP3: أطلق **X-5**.
5. X-0 يسلّم `reports/QA_X_*.md` بعد كل Batch.
