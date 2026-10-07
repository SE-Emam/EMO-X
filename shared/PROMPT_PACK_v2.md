# PROMPT_PACK v2 — Latin-Language Additions (EMO Benchmark Skills)

> Version `v2` — 2026-10-07 (P1: عائلات اللغات الإسبانية والبرتغالية).
> `shared/PROMPT_PACK_v1.md` stays byte-frozen (T2–T8, R1–R12, H1–H6
> unchanged). This file documents ONLY the v2 additions below.
> Any change to any string below (even whitespace) = new version (`v3`) +
> full re-baseline of all models. Reports must state the PROMPT_PACK
> version. Rounds run with mixed versions are void (identical-prompt
> rule, PLAN §0.2). Adding families changes `prompt_pack_sha256` and
> `harness_sha256` — v1 baselines are NOT directly comparable (B58);
> a full re-baseline is required.

Code tests use **no system prompt** (user message only, `temp=0.4`).

## T-group additions (Spanish + Portuguese closure explanations)

- **T9** (user): `Explica en español: ¿qué es el concepto de closure en JavaScript?`
- **T10** (user): `Explica em português: o que é o conceito de closure em JavaScript?`

## Oracle rule (semantic, not form-only)

Unlike the v1 T5 gate (`arabic_ratio > 0.3` alone), T9/T10 pair a
word-level language ratio with a semantic checklist — a reply in the
right script but off-topic must FAIL:

- **T9**: `spanish_ratio > 0.10` (distinctive words such as
  el/la/que/una/función/código) AND all of:
  `función` + (`ámbito`/`alcance`) + (`conserva`/`recuerda`) +
  (`ejemplo`/`código`).
- **T10**: `portuguese_ratio > 0.10` AND all of:
  `função` + `escopo` + `mantém` + (`exemplo`/`código`).
- **T5/T6** (v1 prompts untouched): keep the legacy ratio gates and add
  an additive semantic signal — closure keywords
  (`function`/`scope`/`lexical`/`مثال`, ≥2 hits) for T5, and
  function-reference + description/illustration groups for T6.

## Registry

- `suites/code-bench-25/cases.py`: `FAMILY_IDS` (+`T9`, `T10`),
  `prompt_messages` (+`T9_PROMPT`, `T10_PROMPT`).
- `suites/code-bench-25/manifests/T9.json`, `T10.json`
  (same Task DSL schema as `T5.json`, `prompt_pack: v2`).
- `suites/code-bench-25/executor.py`: `check_family` branches
  `T9`/`T10`, strengthened `T5`/`T6`.
- `shared/run.py`: `t9_spanish`/`t10_portuguese` + `CODE25_ORDER`
  entries (`T9_spanish_explain`, `T10_portuguese_explain`),
  mirrored `T5`/`T6` semantics via `shared/bench_lib.py`.

## P2 — code25 hardening additions (2026-10-07): R13 + A16

> v1 strings stay byte-frozen. This section documents ONLY the P2
> additions below. Any change to any string below (even whitespace) =
> new version (`v3`) + full re-baseline of all models. Adding families
> changes `prompt_pack_sha256` and `harness_sha256` — v1/v2 baselines
> are NOT directly comparable (B58); a full re-baseline is required.

Code tests use **no system prompt** (user message only, `temp=0.4`).

- **R13** (user): `Return ONLY a Dockerfile (no markdown, no explanation) for a Python app that: uses base image python:3.12-slim, sets WORKDIR to /app, copies requirements.txt and runs pip install, and sets a CMD. Pin the base image tag (do not use latest).`
- **A16** (user): `Write Python code with: import asyncio, async def fetch(x) returning x*2, and async def fetch_all() returning await asyncio.gather(fetch(1), fetch(2)). Return ONLY code, no explanation.`

## Oracle rules (P2)

- **R13** (strict text-structural, deterministic, no execution):
  `FROM python:3.12-slim` AND (`WORKDIR` + `/app`) AND (`COPY` +
  `requirements`) AND (`RUN` + `pip install`) AND `CMD` must all hold,
  AND `latest` must be absent (unpinned base tag fails).
- **A16** (real executive oracle via sandbox, like `T6`):
  `asyncio.gather` present AND `fetch(1)`/`fetch(2)` present AND
  `asyncio.run(fetch_all()) == [2, 4]` (prints `ASYNC_OK`).

## Registry (P2)

- `suites/code-bench-25/cases.py`: `FAMILY_IDS` (+`R13`, `A16` → 29),
  `prompt_messages` (+`R13_PROMPT`, `A16_PROMPT`).
- `suites/code-bench-25/manifests/R13.json`, `A16.json`
  (same Task DSL schema as `T9.json`, `prompt_pack: v2`).
- `suites/code-bench-25/executor.py`: `check_family` branches
  `R13`/`A16`.
- `shared/run.py`: `r13_docker`/`a16_async` + `CODE25_ORDER`
  entries (`R13_docker`, `A16_async` → 29).
