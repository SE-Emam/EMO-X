"""EMO-X code-bench-25 canonical cases (PROMPT_PACK v1, FROZEN).

Every prompt string below is a byte-identical COPY of the prompt used by
the legacy runner in shared/run.py (CODE25_ORDER t*/r*/h* functions) and
documented in shared/PROMPT_PACK_v1.md. NEVER rephrase: any change
(including whitespace) requires a new PROMPT_PACK version plus a full
re-baseline, otherwise the round is void.

This module holds ONLY prompt builders + oracle checks. Execution goes
through shared/sandbox.py (see executor.py). Scoring is owned by X-3;
this module emits raw observations only.
"""

FAMILY_IDS = (
    "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10",
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11",
    "R12", "R13",
    "H1", "H2", "H3", "H4", "H5", "H6",
    "A16",
)

# P1 (PROMPT_PACK v2, 2026-10-07): Latin-language closure-explanation
# families. New prompts only — v1 strings above are untouched.
T9_PROMPT = "Explica en espa\u00f1ol: \u00bfqu\u00e9 es el concepto de closure en JavaScript?"
T10_PROMPT = "Explica em portugu\u00eas: o que \u00e9 o conceito de closure em JavaScript?"

# P2 (PROMPT_PACK v2, 2026-10-07): code25 hardening families.
R13_PROMPT = ("Return ONLY a Dockerfile (no markdown, no explanation) for a Python app "
              "that: uses base image python:3.12-slim, sets WORKDIR to /app, copies "
              "requirements.txt and runs pip install, and sets a CMD. "
              "Pin the base image tag (do not use latest).")
A16_PROMPT = ("Write Python code with: import asyncio, async def fetch(x) returning x*2, "
              "and async def fetch_all() returning await asyncio.gather(fetch(1), fetch(2)). "
              "Return ONLY code, no explanation.")

# Frozen code fragments embedded inside prompts (copied from shared/run.py).
T3_BUGGY = "def is_even(n):\n    return n / 2 == 0"
R6_ORIG = ("def total(items):\n    s = 0\n    for i in items:\n"
           "        s += i\n    return s\n")
H6_BUGGY = ("def first_occurrence(a, x):\n    lo, hi = 0, len(a) - 1\n"
            "    while lo <= hi:\n        mid = (lo + hi) // 2\n"
            "        if a[mid] == x:\n            return mid\n"
            "        elif a[mid] < x:\n            lo = mid + 1\n"
            "        else:\n            hi = mid - 1\n    return -1")


def _user(content):
    return [{"role": "user", "content": content}]


def prompt_messages(family):
    """Return the frozen chat message list for a canonical instance."""
    if family == "T2":
        return _user(
            "Write a Python function fib(n) that returns the nth Fibonacci number "
            "(0-indexed, iterative). Return ONLY code, no explanation.")
    if family == "T3":
        return _user(
            "This Python function is buggy:\n" + T3_BUGGY +
            "\nReturn ONLY the fixed function code, no explanation.")
    if family == "T4":
        return _user(
            "Write a JavaScript function sumArr(arr) that returns the sum of an "
            "array of numbers. Return ONLY code, no explanation.")
    if family == "T5":
        return _user(
            "اشرح باللغة العربية: ما هو الـ closure في JavaScript؟")
    if family == "T6":
        return _user(
            "اكتب دالة Python باسم اجمع(a, b) ترجع مجموعهما، واشرح عملها باللغة العربية.")
    if family == "T7":
        return _user(
            'Return ONLY valid JSON, no markdown, no explanation: {"name": a programmer '
            'name, "languages": exactly 3 programming languages, "years": an integer}.')
    if family == "T8":
        return _user(
            "Output ONLY a Python file content (no markdown, no explanation) that: "
            "1) defines add(a,b), 2) prints add(2,3) under if __name__ == '__main__', "
            "3) uses no imports.")
    if family == "T9":
        return _user(T9_PROMPT)
    if family == "T10":
        return _user(T10_PROMPT)
    if family == "R1":
        return _user(
            "Write a COMPLETE Rust program with fn is_prime(n: u64) -> bool and fn main "
            "that asserts is_prime(7) and !is_prime(8) then prints PRIME_OK. "
            "Return ONLY code, no explanation.")
    if family == "R2":
        return _user(
            "Table users(id INTEGER PRIMARY KEY, name TEXT, age INTEGER) has rows: "
            "(1,'Ali',25),(2,'Sara',35),(3,'Omar',40). "
            "Return ONLY the SQLite SELECT query (no markdown, no explanation) that "
            "returns names of users older than 30 ordered by age ascending.")
    if family == "R3":
        return _user(
            "List the exact git commands, one per line, no explanation, to: clone "
            "https://github.com/x/y.git, create branch feat-z, stage all, commit "
            "with message 'feat: z', push the branch to origin.")
    if family == "R4":
        return _user(
            "Return ONLY vercel.json (no markdown, no explanation) for a Vite SPA "
            "that rewrites all routes to /index.html.")
    if family == "R5":
        return _user(
            "Write a JavaScript async function getActiveUsers using supabase-js that "
            "selects id and name from table 'users' where active is true, with error "
            "handling. Return ONLY code, no explanation.")
    if family == "R6":
        return _user(
            "File calc.py contains:\n" + R6_ORIG +
            "\nChange: rename function total to sum_all (update definition only, "
            "keep body). Return ONLY a unified diff (diff -u format), no explanation.")
    if family == "R7":
        return _user(
            "You have a function calculator.add(a, b). To call it for a=17, b=25 reply "
            "ONLY in this exact format with no extra text:\n"
            "<tool_call>\n<function=calculator.add>\n<parameter=a>\n17\n</parameter>\n"
            "<parameter=b>\n25\n</parameter>\n</function>\n</tool_call>")
    if family == "R8":
        return _user(
            "SKILL conventional-commit: messages must match 'type(scope): subject' where "
            "type is one of feat/fix/docs/refactor/test, subject is lowercase, no "
            "trailing period, max 72 chars total. Write ONLY the commit message for: "
            "add login rate limiting to the auth module.")
    if family == "R9":
        return _user(
            "Return ONLY an HTML file (no markdown, no explanation) with embedded "
            "<style> showing a centered blue button labeled 'Click me' using flexbox.")
    if family == "R10":
        return _user(
            "Return ONLY a React functional component named Counter using useState "
            "starting at 0, with a button that increments the count. No explanation.")
    if family == "R11":
        return _user(
            "Write a TypeScript interface User {name: string; age: number} and a function "
            "greet(u: User): string returning 'Hello, NAME'. Return ONLY code, no explanation.")
    if family == "R12":
        return _user(
            "Postgres table products(id SERIAL PRIMARY KEY, name TEXT, price NUMERIC) "
            "has rows: (1,'Keyboard',50),(2,'Mouse',25),(3,'Monitor',200). "
            "Return ONLY the SQL query (no markdown, no explanation) returning names of "
            "products cheaper than 100 ordered by price DESC.")
    if family == "R13":
        return _user(R13_PROMPT)
    if family == "H1":
        return _user(
            "How many 5-digit numbers have strictly increasing digits (left to right)? "
            "Be concise and give the final integer answer clearly.")
    if family == "H2":
        return _user(
            "Find all integer pairs (x, y) with x >= 0, y >= 0 satisfying "
            "x^2 + y^2 = 2025. Be concise and list every solution.")
    if family == "H3":
        return _user(
            "What is the remainder when 3^100 is divided by 7? "
            "Be concise and state the final remainder clearly.")
    if family == "H4":
        return _user(
            "Write a Python function longest_pal(s) returning the longest palindromic "
            "substring of s. Return ONLY code, no explanation.")
    if family == "H5":
        return _user(
            "Write a Python class TokenBucket(rate, capacity) with methods allow() -> bool "
            "and wait_time() -> float implementing the token bucket algorithm using "
            "time.monotonic. Return ONLY code, no explanation.")
    if family == "H6":
        return _user(
            "This binary search returns ANY occurrence, but we need the FIRST occurrence "
            "of x in sorted list a (with duplicates). Fix it. Test: "
            "first_occurrence([1,2,2,2,3],2) must be 1, "
            "first_occurrence([1,2,2,2,3],4) must be -1. "
            "Return ONLY the fixed function code, no explanation.\n" + H6_BUGGY)
    if family == "A16":
        return _user(A16_PROMPT)
    raise KeyError("unknown code-bench-25 family: %r" % (family,))


# Chat-call options per family (copied from shared/run.py budgets/routing).
# T/R use OpenAI-compatible path (temp 0.4); H1-H3 use the native endpoint
# with think=False and larger num_predict budgets.
CHAT_OPTIONS = {
    "H1": {"think": False, "num_predict": 600},
    "H2": {"think": False, "num_predict": 1400},
    "H3": {"think": False, "num_predict": 600},
}

CODE_TEMP = 0.4


def chat_options(family):
    """Return extra chat kwargs for a family (temp + routing flags)."""
    opts = dict(CHAT_OPTIONS.get(family, {}))
    opts.setdefault("temp", CODE_TEMP)
    return opts


def prompt_text(family):
    """Return the single user prompt text for hashing/spot-checks."""
    msgs = prompt_messages(family)
    return msgs[0]["content"]
