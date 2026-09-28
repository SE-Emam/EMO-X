---
name: code-bench-25
description: The 25-test code pack (T/R/H) — real execution of every answer with documented strict gates. Use it to compare any model before adopting it.
---

![EMO-X banner — Execution · Measurement · Observability](../src/emo-x-banner.png)

```text
######  #    #   ####   #    #
#       ##  ##  #    #   #  #
#####   # ## #  #    #    ##
#       #    #  #    #   #  #
######  #    #   ####   #    #
Measure what agents accomplish — not what they say
```

# Code test 25 (code-bench-25)

## What is it?

25 tests that really execute the model's answer (real compilers and
interpreters), not eyeballing. Every test: frozen prompt from
`shared/PROMPT_PACK_v1.md` + execution check + raw JSON result.

## Pack contents (25 tests)

- **T (basic + Arabic):** T2 Fibonacci, T3 `is_even` fix, T4 JS sum, T5 Arabic explanation, T6 Arabic code, T7 JSON conformance, T8 file task.
- **R (realistic):** R1 complete Rust program, R2 SQLite query, R3 git commands,
  R4 vercel.json, R5 supabase-js function, R6 unified diff,
  R7 strict-format tool call, R8 commit message, R9 HTML/CSS page,
  R10 React component, R11 TypeScript check, R12 Postgres query.
- **H (hard):** H1 increasing digits, H2 Diophantine equation, H3 modular remainder,
  H4 longest palindrome, H5 token bucket, H6 first occurrence.

Note: numbering starts at T2 (seven T + twelve R + six H = 25 tests).

## Methodology notes (do not change without a new PROMPT_PACK version)

1. **T5 gate strictness:** passing requires `arabic_ratio > 0.3` — mixed
   replies (short Arabic + long English) fail by design. This measures
   genuine Arabic explanation.
2. **Corrected R6 check:** applying the diff is not enough; the resulting
   file must contain `def sum_all` **and** the original body (`s += i`).
   An applying-but-wrong diff = fail.
3. **Corrected R10 check:** case-insensitive match of `useState(0)` with no
   spaces, plus `onClick`, `setCount`, name `Counter`, and `export`.
   Prevents false positives.
4. **Corrected R12 check:** only the expected rows `["Keyboard", "Mouse"]`
   (cheaper than 100 ordered DESC: 50 then 25) — any other order = fail.
5. **H3 triple-run rule:** after observed H3 instability, single H3 runs
   are **non-admissible**. Run `--trials 3` and take majority/mean.
6. **`think:false` for math:** H1–H3 run via the native endpoint with
   `think=false` (and `num_predict=1400` for H2). Long reasoning adds
   noise and breaks numeric answer extraction.

## Run

```bash
# Full suite against a Kaggle tunnel
python shared/run.py --backend kaggle --base-url "$BASE_URL" \
    --model "$MODEL" --suite code25 --out results/

# Subset + 3 trials (required for H3 verdicts)
python shared/run.py --suite code25 --only T5,R7,H3 --trials 3 --out results/

# Commercial / local OpenAI-compatible endpoint
python shared/run.py --backend openai-generic --suite code25 --out results/
```

## Model capability (who may run this)

Text-generation models only (`--model-type llm/chat/code/reasoning/
math/agentic`, default modalities `text`). Embedding, decision (Jev),
image, video, audio, CNN, or RL types are **refused before the first
call** (`ModelCapabilityDenied`) — scored zeros from an incapable
model are inadmissible. See `docs/model-onboarding.md` for the
19-type matrix and external-standard pointers (MTEB, TypeSafe, ...).

## Verification

```python
# Every answer executes in a real toolchain (bench_lib verifiers):
ok, log = run_py(code, "assert fib(0)==0 and fib(10)==55; print('FIB_OK')")
ok, log = run_js(code, "if (sumArr([1,2,3,4])!==10) throw 1; console.log('JS_OK')")
ok, log = run_rust(code)          # rustc -O, program must print PRIME_OK
ok, log = verify_tsc(code)        # tsc --noEmit --strict (+ static fallback)
ok, log = verify_patch("calc.py", orig, diff, must_contain=("def sum_all", "s += i"))
```

## Reports

Raw JSON results in `results/` (never edit them) + `pass/total` summary.
The report must state: PROMPT_PACK version, backend, temperature, trial
count, hardware.
