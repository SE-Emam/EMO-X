# PROMPT_PACK v1 — Frozen Prompts (EMO Benchmark Skills)

> Version `v1` — 25/09/2026. Every string below is byte-frozen. Any change
> (even whitespace) = new version (`v2`) + full re-baseline of all models.
> Reports must state the PROMPT_PACK version. Rounds run with mixed versions
> are void (identical-prompt rule, PLAN §0.2).

Code tests use **no system prompt** (user message only, `temp=0.4` unless noted).
Math tests H1–H3 use the **native** endpoint with `think=false`
(`num_predict=600`, H2 `num_predict=1400`).
The agent loop uses the SYSTEM + TASK below with `temp=0.4`, `think=true`,
`num_predict=800`, `MAX_STEPS=15`.

## T-group (basic code + Arabic)

- **T2** (user): `Write a Python function fib(n) that returns the nth Fibonacci number (0-indexed, iterative). Return ONLY code, no explanation.`
- **T3** (user): `This Python function is buggy:` + newline + `def is_even(n):\n    return n / 2 == 0` + newline + `Return ONLY the fixed function code, no explanation.`
- **T4** (user): `Write a JavaScript function sumArr(arr) that returns the sum of an array of numbers. Return ONLY code, no explanation.`
- **T5** (user): `اشرح باللغة العربية: ما هو الـ closure في JavaScript؟`
- **T6** (user): `اكتب دالة Python باسم اجمع(a, b) ترجع مجموعهما، واشرح عملها باللغة العربية.`
- **T7** (user): `Return ONLY valid JSON, no markdown, no explanation: {"name": a programmer name, "languages": exactly 3 programming languages, "years": an integer}.`
- **T8** (user): `Output ONLY a Python file content (no markdown, no explanation) that: 1) defines add(a,b), 2) prints add(2,3) under if __name__ == '__main__', 3) uses no imports.`

## R-group (real-world code)

- **R1** (user): `Write a COMPLETE Rust program with fn is_prime(n: u64) -> bool and fn main that asserts is_prime(7) and !is_prime(8) then prints PRIME_OK. Return ONLY code, no explanation.`
- **R2** (user): `Table users(id INTEGER PRIMARY KEY, name TEXT, age INTEGER) has rows: (1,'Ali',25),(2,'Sara',35),(3,'Omar',40). Return ONLY the SQLite SELECT query (no markdown, no explanation) that returns names of users older than 30 ordered by age ascending.`
- **R3** (user): `List the exact git commands, one per line, no explanation, to: clone https://github.com/x/y.git, create branch feat-z, stage all, commit with message 'feat: z', push the branch to origin.`
- **R4** (user): `Return ONLY vercel.json (no markdown, no explanation) for a Vite SPA that rewrites all routes to /index.html.`
- **R5** (user): `Write a JavaScript async function getActiveUsers using supabase-js that selects id and name from table 'users' where active is true, with error handling. Return ONLY code, no explanation.`
- **R6** (user): `File calc.py contains:` + newline + `def total(items):\n    s = 0\n    for i in items:\n        s += i\n    return s\n` + newline + `Change: rename function total to sum_all (update definition only, keep body). Return ONLY a unified diff (diff -u format), no explanation.`
- **R7** (user):
  `You have a function calculator.add(a, b). To call it for a=17, b=25 reply ONLY in this exact format with no extra text:` + newline
  `<tool_call>` + newline + `<function=calculator.add>` + newline + `<parameter=a>` + newline + `17` + newline + `</parameter>` + newline + `<parameter=b>` + newline + `25` + newline + `</parameter>` + newline + `</function>` + newline + `</tool_call>`
- **R8** (user): `SKILL conventional-commit: messages must match 'type(scope): subject' where type is one of feat/fix/docs/refactor/test, subject is lowercase, no trailing period, max 72 chars total. Write ONLY the commit message for: add login rate limiting to the auth module.`
- **R9** (user): `Return ONLY an HTML file (no markdown, no explanation) with embedded <style> showing a centered blue button labeled 'Click me' using flexbox.`
- **R10** (user): `Return ONLY a React functional component named Counter using useState starting at 0, with a button that increments the count. No explanation.`
- **R11** (user): `Write a TypeScript interface User {name: string; age: number} and a function greet(u: User): string returning 'Hello, NAME'. Return ONLY code, no explanation.`
- **R12** (user): `Postgres table products(id SERIAL PRIMARY KEY, name TEXT, price NUMERIC) has rows: (1,'Keyboard',50),(2,'Mouse',25),(3,'Monitor',200). Return ONLY the SQL query (no markdown, no explanation) returning names of products cheaper than 100 ordered by price DESC.`

## H-group (hard: math + algorithms)

- **H1** (user, native `think=false`): `How many 5-digit numbers have strictly increasing digits (left to right)? Be concise and give the final integer answer clearly.`
- **H2** (user, native `think=false`, `num_predict=1400`): `Find all integer pairs (x, y) with x >= 0, y >= 0 satisfying x^2 + y^2 = 2025. Be concise and list every solution.`
- **H3** (user, native `think=false`): `What is the remainder when 3^100 is divided by 7? Be concise and state the final remainder clearly.`
- **H4** (user): `Write a Python function longest_pal(s) returning the longest palindromic substring of s. Return ONLY code, no explanation.`
- **H5** (user): `Write a Python class TokenBucket(rate, capacity) with methods allow() -> bool and wait_time() -> float implementing the token bucket algorithm using time.monotonic. Return ONLY code, no explanation.`
- **H6** (user): `This binary search returns ANY occurrence, but we need the FIRST occurrence of x in sorted list a (with duplicates). Fix it. Test: first_occurrence([1,2,2,2,3],2) must be 1, first_occurrence([1,2,2,2,3],4) must be -1. Return ONLY the fixed function code, no explanation.` + newline + `def first_occurrence(a, x):\n    lo, hi = 0, len(a) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if a[mid] == x:\n            return mid\n        elif a[mid] < x:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1`

## Agent loop (frozen SYSTEM + TASK)

SYSTEM:
`You are a coding agent inside a repo at /repo. Fix the failing tests. Rules: NEVER modify shop/tests/ or shop/config.py or shop/vendor_dump.py. The archived notes in legacy/notes.md may help (if present). Work ONLY with these tools, one call per message, exact format:` + newline
`<tool_call>` + newline + `<function=read>` + newline + `<parameter=path>shop/taxes.py</parameter>` + newline + `</function>` + newline + `</tool_call>` + newline
`EXACT parameter names: ls uses path; read uses path; run uses cmd; edit uses path+old+new.` + newline
`run allows only pytest/py_compile/ls/cat in /repo. edit fails if old not found verbatim.` + newline
`When tests pass, reply FINAL: <one-line summary> with NO tool call. Stop then (A14).`

TASK (user):
`Pip-free repo. Run the test suite: ` + `` `python3 -m pytest shop/tests/ -x -q` `` + `. One or more tests fail. Inspect the repo, locate the bug, fix source files, re-run tests until green. Do not stop before tests pass.`

## The `<parameter=P>` lesson (read before judging tool calls)

The harness parses tool calls with this exact grammar:

```
<tool_call>
<function=NAME>
<parameter=P>value</parameter>   # one tag per parameter, name after `=`
</function>
</tool_call>
```

Observed failure modes (all count as **no-tool-call**, never partial credit):

1. JSON-style tags: `<parameter name="path">…</parameter>` — does not match `<parameter=([\w]+)>`.
2. Bare tags: `<path>…</path>` — no `<parameter=…>` wrapper, never parsed.
3. Markdown code-fence around the call — the regex still matches inside fences, so
   fences alone do NOT break parsing; the parameter names inside must still be exact.
4. Wrong parameter names (`file` instead of `path`, `command` instead of `cmd`,
   `old_string` instead of `old`) — parses, then the tool reports
   `ERROR: no such file` / missing-arg behavior and burns a step.

R7 exists specifically to test this: the model must echo the
`<parameter=a>` / `<parameter=b>` form byte-exact. A model that otherwise codes
well but "improves" the XML fails R7 and will thrash in the agent loop — that is
the intended signal, not a harness bug. Keep the grammar strict; document
failures as tool-discipline failures (A6).
