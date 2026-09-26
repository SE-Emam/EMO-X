# EMO-X — Review Plan

> Complements `PLAN-X.md` (build) and `AGENTS-X.md` (execution): this plan
> governs **verification** before push, after push, and periodically.
> Normative reference: `SPEC.md` + `DENOMINATORS.md`.
> Executor: the X-0 monitor role (human or agent) — reports go in `reports/QA_X_*.md`.

---

## 1. Review types

| # | Review | When | Goal | Output |
|---|---|---|---|---|
| R1 | Pre-push | Before every `git push` | No broken contracts, no secrets, tests green | `reports/QA_X_prepush_<date>.md` + GO/NO-GO |
| R2 | Post-push/CI | After every merge to `main` | Clean-clone works (`clone → self-test → run_all`) | Green CI or a fix ticket |
| R3 | Official baseline review | Before any OFFICIAL claim | Full §B59 conditions (n≥3, frozen, seeds, manifests, coverage≥95%) | `reports/QA_X_baseline_<model>.md` |
| R4 | Benchmark self-review | Monthly or every 5 models | Benchmark health: saturation/discrimination/flakiness/contamination (§§11–12, C48–C53) | `reports/QA_X_health_<date>.md` + retire/rotate decisions |

---

## 2. R1 checklist — pre-push (mandatory gate)

- [ ] `python3 tests/run_all.py` → PASS all suites (currently 5/5 = 517).
- [ ] `python3 shared/run.py --self-test` → PASS (currently 10/10, fail-closed).
- [ ] Frozen contracts intact: `PROMPT_PACK_v1` header, `REPORT_TEMPLATE` (8 sections in order), `report.py:17 + :86`, all 7 fixtures sha256-identical to originals, legacy `run/bench_lib/backends` logic unmodified (CLI additions only).
- [ ] No secrets: `rg -i "api[_-]?key|token|secret|password" --glob '!reports/*'` clean, and `.env` untracked (`.gitignore`).
- [ ] Ownership: new files only inside their owners' directories (`AGENTS-X.md` §3).
- [ ] Any change to (task/oracle/scoring/prompt/harness) ← version bump + re-baseline (§45), else NO-GO.
- [ ] `git status` free of temp files (`__pycache__/`, trial `results/raw/RUN-*/` deleted or deliberately excluded).

**Result:** GO (push) or NO-GO (numbered fix list blocking the push).

---

## 3. R2 checklist — post-push (clean clone)

```bash
git clone <URL> emo-x && cd emo-x
python3 shared/run.py --self-test        # must: PASS
python3 tests/run_all.py                 # must: PASS all suites
python3 shared/run.py --suite code25 --trials 1 --out /tmp/e2e/
ls /tmp/e2e/RUN-*/  # manifest.json + events.jsonl + responses.jsonl + environment.json
```

Any failure here = P0 ticket (a broken environment voids every later result — §B58).

---

## 4. R3 checklist — official baseline review (before publishing any number)

- [ ] `n ≥ 3` trials per task + recorded seeds + model identifier + runtime versions.
- [ ] Identical triple freeze: `PromptHash + HarnessHash + TaskManifestHash` (§B58) — otherwise the comparison is labeled NON-COMPARABLE.
- [ ] `Coverage ≥ 0.95` (§B59), else PILOT not OFFICIAL.
- [ ] Safety gate: `CSVRate = 0`, else NOT RANKABLE (§B56) — metrics shown, single number withheld.
- [ ] Full public report (§B60): Pass Rate, Partial, Generalization, Tool Discipline, Recovery, Efficiency, Calibration, Safety, Long-Horizon, Human-Minutes, Failure Fingerprint, 95% CI (family bootstrap B54), Coverage, Health — **never display one number alone** (§B61).
- [ ] `raw/` results preserved unmodified, derived outputs regeneratable (§33).

---

## 5. R4 checklist — benchmark self-health (anti-aging)

| Metric | Threshold | Action on breach |
|---|---|---|
| Saturation (§11, C49/C71) | `p̄ > 0.95` across ≥3 models | Task becomes historical; activate a replacement family |
| Discrimination (C50/C70) | `D ≈ 0` or permanent NA | Reword or drop from weighting |
| Flakiness (C48/C69) | `4p(1-p) > 0.25` | Freeze the task until the source is fixed |
| Contamination proxy (B13) | Large sustained positive `NoveltyGap` | Rotate new instances (new seed) |
| Judge reliability (C52) | `< 0.90` | LOW-CONFIDENCE; never use as sole headline |
| Overall health (C72) | `< 0.80` | Run NOT RANKABLE until recovery (§B56) |

---

## 6. Monitor powers (instant veto — from `AGENTS-X.md` §5)

1. Writing outside ownership or modifying a frozen contract.
2. A scoring formula with no golden test or no `D=0 ⇒ NA` coverage.
3. Merging `ERROR/VOID` into a performance denominator, or double-counting within one axis.
4. A number with no CI/Coverage/Health.
5. Guessing under ambiguity instead of `INSUFFICIENT_EVIDENCE` (DEN §C88).

---

## 7. Report template (mandatory for every R)

`reports/QA_X_<type>_<date>.md`: scope → checks (command + result) → verdict table (PASS/FAIL/OPEN with `file:line` evidence) → GO/NO-GO verdict → numbered fix list → INSUFFICIENT_EVIDENCE items.

---

## 8. Operating schedule

1. **Today:** R1 on the current state (all WPs closed — re-confirm push GO).
2. **Push day:** R2 after first push (clean clone).
3. **First real baseline:** R3 before publishing any OFFICIAL number.
4. **Then:** R4 monthly.
