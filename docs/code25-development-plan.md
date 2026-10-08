# code25 Development Audit & Plan — 2026-10-08

## Scope and method

This is a read-only audit of `suites/code-bench-25/` and the companion
`code-bench-25/` documentation. I inspected the suite source, all 29 task
manifests, the suite skill, related tests, the raw-attempt contract, and the
shared scoring helpers. No tests, executor behavior, or scoring logic were
modified or run during this phase.

The current suite contains **29 task families**, not 25: T2–T10 (9), R1–R13
(13), H1–H6 (6), and A16 (1). Only H3 has dynamic `perturbed` and `novel`
variants; the other 28 families are canonical-only. This makes the name
“code-bench-25” and some current test/doc wording historical rather than an
accurate count.

## Phase 1 — Discovery and structural audit

### 1.1 File inventory

Tracked source and documentation files:

| File | Lines | Purpose |
|---|---:|---|
| `code-bench-25/SKILL.md` | 94 | Describes the pack, methodology, invocation, model eligibility, and report requirements. |
| `suites/code-bench-25/cases.py` | 253 | Holds canonical prompts, chat options, prompt accessors, and fixed input fragments. |
| `suites/code-bench-25/executor.py` | 1,135 | Implements prompt extraction, family-specific oracles, H3 dynamic dispatch, attempt creation, and raw-run persistence. |
| `suites/code-bench-25/instances.py` | 40 | Builds canonical instance IDs and prompt/manifest hash records. |
| `suites/code-bench-25/t9_calibration.json` | 0 newline-terminated lines; 6,349 bytes | Stores a one-line JSON calibration set of 8 positive and 8 negative Spanish closure explanations. |
| `suites/code-bench-25/manifests/` | 29 files; detailed below | Declares task identity, category, capabilities, prompt, generator, execution type, oracle summary, timeouts, and scoring weights. |

The working tree also contains nine untracked-by-source Python bytecode files
under `suites/code-bench-25/__pycache__/`: compiled `cases.py`, `executor.py`,
and `instances.py` artifacts for Python 3.11, 3.12, and 3.14. These are runtime
caches, not source or test inputs, and are excluded from the functional
inventory above.

Manifest line counts and purposes:

| Manifest | Lines | Purpose |
|---|---:|---|
| `A16.json` | 54 | Async Python `asyncio.gather` task. |
| `H1.json` | 57 | Counting five-digit numbers with strictly increasing digits. |
| `H2.json` | 57 | Enumerating nonnegative integer solutions of a sum-of-squares equation. |
| `H3.json` | 101 | Modular arithmetic task with parametric generated variants. |
| `H4.json` | 54 | Longest palindromic substring implementation. |
| `H5.json` | 54 | Python token-bucket implementation. |
| `H6.json` | 55 | Binary-search repair to return the first duplicate occurrence. |
| `R1.json` | 56 | Rust primality implementation and compilation/execution check. |
| `R2.json` | 53 | SQLite query over a small in-memory users table. |
| `R3.json` | 53 | Git command sequence for clone, branch, stage, commit, and push. |
| `R4.json` | 53 | Vercel SPA rewrite configuration. |
| `R5.json` | 53 | Supabase JavaScript query with filtering and error handling. |
| `R6.json` | 56 | Unified diff changing a Python function name. |
| `R7.json` | 53 | Strict-format calculator tool-call serialization. |
| `R8.json` | 53 | Conventional commit message generation. |
| `R9.json` | 53 | HTML/CSS centered blue button. |
| `R10.json` | 53 | React counter component shape. |
| `R11.json` | 56 | Strict TypeScript interface/function compilation. |
| `R12.json` | 56 | PostgreSQL query against a scratch instance. |
| `R13.json` | 54 | Dockerfile structure and base-tag task. |
| `T2.json` | 54 | Python Fibonacci implementation. |
| `T3.json` | 54 | Python `is_even` bug fix. |
| `T4.json` | 57 | JavaScript array summation. |
| `T5.json` | 53 | Arabic-language closure explanation. |
| `T6.json` | 54 | Python addition function with Arabic explanation. |
| `T7.json` | 53 | Exact-shape JSON response. |
| `T8.json` | 53 | Python file-content task with execution and no-import requirement. |
| `T9.json` | 54 | Spanish-language closure explanation. |
| `T10.json` | 54 | Portuguese-language closure explanation. |

### 1.2 Manifest analysis

Every manifest sets `suite` to `code-bench-25`, names the suite executor,
declares `network.allowed: false`, `filesystem.sandbox_only: true`, supplies
the common forbidden paths (`/etc`, `/root`, `/home`, `~/.ssh`,
`/var/run/secrets`), and includes positive `generation_seconds` and
`execution_seconds` budgets. The oracle `type` is `"deterministic"` for all
29. Most tasks use frozen canonical instances; H3 is the single parametric
generator. All manifests weight correctness 1.0; H3 also declares explanation
and verification weights, though the executor still produces a binary result.

| ID / name | Category; capability being sampled | Execution input type / language | Oracle and evaluation | Execution / generation budget | Extra runtime requirement | Variants |
|---|---|---|---|---:|---|---|
| T2 `python_fib` | basic-coding; iterative algorithm | Python | Execute `fib` on 0, 1, 10; require `FIB_OK`. | 30s / 120s | — | canonical |
| T3 `bugfix` | basic-coding; arithmetic bug repair | Python | Execute repaired `is_even` on even and odd values; require `FIX_OK`. | 30s / 120s | — | canonical |
| T4 `javascript` | basic-coding; array reduction | JavaScript | Execute with Node against a fixed sum; require `JS_OK`. | 30s / 120s | `node` | canonical |
| T5 `arabic_explain` | Arabic; language and closure concept | Text | Arabic character/word ratio plus deterministic closure-semantic checklist. | 30s / 120s | — | canonical |
| T6 `arabic_code` | Arabic + basic coding; bilingual code generation | Python | Execute Arabic-named function and require Arabic ratio/semantic groups. | 30s / 120s | — | canonical |
| T7 `json_struct` | basic-coding; structured output | Text / JSON | Parse first balanced JSON object; exact key set, three languages, integer years. | 30s / 120s | — | canonical |
| T8 `file_task` | basic-coding; executable file content | Python | Run extracted code; output must end in `5`; prompt also forbids imports. | 30s / 120s | — | canonical |
| T9 `spanish_explain` | Spanish; language and closure concept | Text | Spanish ratio plus deterministic closure-semantic checklist; calibration fixture has 8 positive and 8 negative replies. | 30s / 120s | — | canonical |
| T10 `portuguese_explain` | Portuguese; language and closure concept | Text | Portuguese ratio plus deterministic closure-semantic checklist. | 30s / 120s | — | canonical |
| R1 `rust` | real-world-coding + systems programming; primality | Rust | Compile with `rustc -O`, execute, and require `PRIME_OK`. | 120s / 120s | `rustc` | canonical |
| R2 `sql` | real-world-coding + SQL; filtering/order | SQLite | Execute query in memory and compare rows to `["Sara", "Omar"]`. | 30s / 120s | Python SQLite | canonical |
| R3 `git` | real-world-coding; ordered CLI workflow | Text / shell command text | Check five required command fragments; commands are not executed. | 30s / 120s | — | canonical |
| R4 `vercel` | real-world-coding; deployment config | Text / JSON | Parse JSON and check a rewrite references `index.html`. | 30s / 120s | — | canonical |
| R5 `supabase` | real-world-coding; client-library usage/error handling | Text / JavaScript | Six lexical signal checks for client, table, select, filter, error, and async usage; code is not run. | 30s / 120s | — | canonical |
| R6 `diff` | real-world-coding; patch generation | Unified diff | Reject obvious path escapes, dry-run/apply patch, check renamed function and body. | 30s / 120s | `patch` | canonical |
| R7 `toolcall` | real-world-coding; tool-call protocol | Text / structured tool call | Require exact tool-call markers/function and parameter values. | 30s / 120s | — | canonical |
| R8 `skill` | real-world-coding; conventional commit convention | Text | Check allowed type, lowercase subject, punctuation, length, and auth/rate-limit keyword. | 30s / 120s | — | canonical |
| R9 `htmlcss` | real-world-coding; simple frontend layout | Text / HTML/CSS | Require button, style, flex centering signal, and blue color signal. | 30s / 120s | — | canonical |
| R10 `react` | real-world-coding + frontend components; stateful UI | Text / JSX | Lexical checks for `useState(0)`, click handler, setter, component/export; not compiled or run. | 30s / 120s | — | canonical |
| R11 `typescript` | real-world-coding; interface and function typing | TypeScript | Run `tsc --noEmit --strict`, with an appended call-site type check; manifest labels dependency `tsc-optional`. | 120s / 120s | `tsc` or documented fallback | canonical |
| R12 `postgres` | real-world-coding + SQL; filtering/order | PostgreSQL | Run against scratch Postgres and require exact `["Keyboard", "Mouse"]` output. | 60s / 120s | `psql-scratch-instance` | canonical |
| R13 `docker_python` | Docker + DevOps; Dockerfile structure | Text / Dockerfile | Text-structural checks for requested directives and rejects substring `latest`; does not parse/build image. | 30s / 120s | — | canonical |
| H1 `increasing_digits` | reasoning; combinatorics | Text | Check that reply contains `126`. | 30s / 120s | — | canonical |
| H2 `diophantine` | reasoning; number theory | Text | Check reply contains `27`, `36`, `45`, and `0`. | 30s / 120s | — | canonical |
| H3 `modular_arithmetic` | reasoning; modular arithmetic/generalization | Text | Deterministic expected-answer check; canonical exponentiation answer is 4. | 30s / 120s | Parametric manifest generator | canonical, perturbed, novel |
| H4 `palindrome` | reasoning + algorithms; string algorithms | Python | Execute multiple examples and require `PAL_OK`. | 60s / 120s | — | canonical |
| H5 `token_bucket` | reasoning + concurrency primitives; rate-limiter algorithm | Python | Execute allow/wait/refill sequence and require `TB_OK`. | 60s / 120s | — | canonical |
| H6 `first_occurrence` | reasoning + algorithms; binary-search edge handling | Python | Execute duplicate, absent, singleton-duplicate, and empty-list examples; require `BS_OK`. | 60s / 120s | — | canonical |
| A16 `async_gather` | async; basic coroutine composition | Python | Require `asyncio.gather` and calls plus execute `fetch_all()` to equal `[2,4]`. | 30s / 120s | — | canonical |

### 1.3 Executor analysis

- **Loading and dispatch:** The executor resolves sibling modules by file path
  under unique names to avoid collisions with other suites’ `cases.py` modules.
  It imports shared `sandbox`, manifests, schemas, reasoning-mode routing, and
  the H3 generator. `prompt_messages()` reads the manifest prompt first, with
  `cases.py` as fallback; prompt-equality tests guard the two sources.
- **Dispatch:** `run_family()` selects canonical prompts for all families.
  Non-canonical variants are routed only for H3; every other unsupported
  family/variant pair raises `TypeError`, allowing the runner to record the
  observation as NA rather than a failure. H3 selects generator subtype from
  `math_subtype` and uses the deterministic expected-value checker.
- **Backends:** Python code, Node JavaScript, Rust, TypeScript, patch, and
  PostgreSQL use the shared Docker sandbox. SQLite is an in-memory local
  database. Text/config/protocol tasks use in-process deterministic checks;
  R3’s Git commands and R5/R10’s framework examples are not actually executed.
- **Isolation:** Executed generated code is routed through `shared/sandbox.py`.
  Patch paths receive a lexical escape check before application inside the
  sandbox. SQL tasks are separately handled: R2 uses Python’s in-memory
  SQLite; R12 uses the scratch PostgreSQL service via the sandbox.
- **Error outcomes:** A pass maps to `PASS`, a false oracle to `FAIL`,
  sandbox timeout to `TIMEOUT`, and missing executor/runtime exceptions to
  `ERROR`. The broad final `except Exception` is reported as a missing-tool /
  harness error, which avoids false success but can obscure whether the
  underlying cause was infrastructure or an implementation defect.
- **Attempt/response records:** Attempts include family/instance/variant,
  trial, status, binary score, eligibility flags, seed, reasoning mode,
  elapsed generation seconds, bounded output log/sample, prompt and manifest
  hashes, and an error when present. Response records retain messages,
  options, full reply, and backend-provided `usage` (which may include token
  data). Raw-run persistence validates the run manifest and attempt records.

### 1.4 Test-case inventory and existing validation

There are **29 canonical family cases** and **2 additional H3 variant classes**
(perturbed and novel), for **31 supported family/variant combinations**.
The H3 generator varies equation surface while preserving the intended
deterministic answer class. The other tasks do not currently provide generated
or adversarial variants.

Existing automated checks include:

- `tests/backends/test_manifest_truth.py`: family/manifest count and ID
  agreement, prompt byte equality, oracle presence, timeout presence,
  forbidden-path presence, and H3 generator metadata.
- `tests/backends/test_suites.py`: legacy prompt equivalence, math routing
  flags, selected passing raw-record cases, a failing H1 example, instance
  hashes, and raw run layout/schema.
- `tests/generators/test_h3_dynamic.py` and
  `tests/generators/test_h3_subtypes.py`: H3 determinism, variant coverage,
  answer correctness/rejection, seed/hash behavior, and subtype selection.
- `tests/harness/test_runner_contract.py` and
  `tests/harness/test_reasoning_mode.py`: unsupported variants as NA and
  family-specific inference options.

The passing raw-record fixture exercises only a subset of families (T2, T7,
R2, R3, R7, R8, H1, H3); it does not provide an explicit canned passing reply
for each of the 29 families. T9 calibration data exists, but the repository
search found no test that loads and evaluates all 16 calibration samples
against the live T9 oracle.

### 1.5 Scoring and metrics

- Family oracle results currently produce a binary score: 1.0 for `PASS`,
  0.0 otherwise. Task manifests declare correctness weight 1.0; H3 declares
  explanation and verification weights as well, but `run_family()` does not
  emit separately scored checkpoints or partial credit.
- Shared scoring supports checkpoint-weighted task scores and strict-pass
  predicates, followed by trial, instance, variant, and family aggregation.
  That capability is broader than the code25 executor output currently
  exercises.
- Available per-attempt metadata: generation latency (`secs`), reasoning
  mode, status/failure class, log/sample, seed, prompt/manifest hashes, and
  error. The response record retains backend-provided usage data. The
  executor does not directly measure sandbox runtime, memory, CPU, or
  complexity, and does not guarantee that each backend reports tokens.

## Phase 2 — Gap analysis

### 2.1 Coverage matrix

Depth refers to the task challenge and oracle discrimination presently
observable in code25, not a general claim about the state of the art.

| Skill dimension | Current tasks | Depth | Gap? |
|---|---|---|---|
| Basic algorithms and implementation | T2, T4, H4, H6 | Basic–intermediate | **Yes:** fixed examples, little input-domain breadth, no adversarial variant outside H3. |
| Bug fixing / debugging | T3, H6 | Basic–intermediate | **Yes:** isolated single-function fixes; no multi-step diagnosis or regression suite. |
| SQL and relational queries | R2, R12 | Basic | **Yes:** one small read-only select each; no joins, transactions, schema migration, query plans, or injection-safe query construction. |
| API/client-library usage | R5 | Basic | **Yes:** lexical signals only; no mocked service, API contract, pagination, retry, or actual error path. |
| Deployment/configuration | R4, R13 | Basic | **Yes:** shape/string checks; no parser, build, deployment behavior, or threat analysis. |
| Frontend/UI | R9, R10 | Basic | **Yes:** static token checks, no rendering, accessibility, or interaction tests. |
| Patch/refactoring | R6 | Basic | **Yes:** one rename-only diff with limited postcondition checks; no multi-file or behavior-preserving refactor. |
| Shell/tool protocol | R3, R7, R8 | Basic | **Yes:** static string/protocol assertions rather than execution in a controlled mock workspace. |
| Type systems / compiled languages | R1, R11, T4 | Basic–intermediate | **Yes:** one Rust program and one TypeScript compile task; little type inference, generics, lifetimes, or error diagnosis. |
| Mathematical reasoning | H1, H2, H3 | Basic–intermediate | **Yes:** fixed arithmetic answers plus H3 generated equations; limited proof/explanation and adversarial distractors. |
| String/sequence algorithms | H4, H6 | Intermediate | **Yes:** selected examples; no scale/performance oracle, Unicode, or broad property generation. |
| Concurrency / async | A16, H5 | Basic | **Yes:** A16 checks a basic gather result; H5 checks sequential token refill, not concurrent access/races. |
| Error handling / resilience | R5 (text checks), R12 (missing-instance behavior in oracle description) | Basic | **Yes:** no systematic injected failure, retry, cleanup, or recovery task family. |
| Security awareness | R13 (rejects `latest` only); R5 (mentions errors) | Minimal | **Critical gap:** no vulnerability identification/fix, input validation, authorization, secret handling, or exploit-resistant regression oracle. |
| Performance / complexity | H4, H6 correctness examples only | None measured | **Critical gap:** no scale-based complexity or resource budget metric. |
| Multi-file / repository work | R6 modifies a single `calc.py` | None | **Critical gap:** no repo navigation, cross-file dependency, test-driven change, or integration behavior. |
| Multilingual programming assistance | T5, T6, T9, T10 | Basic | **Yes:** Arabic, Spanish, Portuguese; each is a narrow closure/code-explanation task without robustness or task diversity. |
| Structured output | T7, R4, R7 | Basic | **Yes:** shape/schema checks; no malformed recovery, nested schema edge cases, or tool-result workflow. |

### 2.2 Strengths

1. **Deterministic, inspectable outcomes:** most code tasks execute in a real
   interpreter/compiler or validate an explicit output shape instead of
   relying on an LLM judge.
2. **Useful task breadth for a compact pack:** includes Python, JavaScript,
   Rust, TypeScript, SQLite, PostgreSQL, patch workflows, CLI protocol,
   frontend, configuration, math, and multilingual prompts.
3. **Integrity and reproducibility controls:** manifest IDs, prompt byte
   equality, canonical instance IDs, hashes, seeded H3 generation, and
   explicit statuses are tested.
4. **H3 generalization precedent:** perturbed/novel H3 instances preserve a
   declared oracle while varying prompts reproducibly.
5. **Sandboxed execution boundary for executed generated code:** execution
   paths route to the shared sandbox, with timeouts and explicit failure on
   unavailable infrastructure rather than silently treating missing tools as
   a pass.

### 2.3 Highest-impact weaknesses and gaps

| Rank | Gap | What is missing and why it matters | Effort |
|---:|---|---|---|
| 1 | Security tasks lack security outcomes | R13 only screens a handful of Dockerfile tokens. Agents are not evaluated on preventing injection, validating untrusted input, authorization boundaries, secret exposure, or safe fixes. This leaves high-impact secure-development behavior unmeasured. | Medium |
| 2 | No repository-scale tasks | The suite has no multi-file task, test discovery, dependency tracing, or integration regression. Real coding agents commonly modify repositories rather than isolated snippets. | Hard |
| 3 | No objective performance/complexity checks | Correct answers can be quadratic or resource-hungry and still pass. Without scaled inputs and resource measurements the pack cannot distinguish efficient implementations. | Hard |
| 4 | Most tasks are canonical-only | H3 is the only task with perturbation/novelty. Single prompt and fixed inputs invite memorization and give little evidence of generalization. | Medium–Hard |
| 5 | Oracle fidelity varies | R3/R5/R9/R10/R13 and some config checks use lexical presence rather than execution/parsing. These can pass semantically incorrect outputs or reject valid alternatives; text criteria also favor specific wording. | Medium |
| 6 | Concurrency and error recovery are shallow | A16 tests one happy-path gather and H5 is sequential. There are no controlled races, cancellation, partial failure, retry/backoff, or cleanup cases, so operational robustness is largely unmeasured. | Medium |
| 7 | Uneven test and documentation coverage | At audit time, only a subset of families had canned raw-record pass fixtures; T9's 16-item calibration set lacked a regression test, and the skill page still said “25 tests.” Sprint 1 has since added T9/all-family oracle fixtures and refreshed the current family-count documentation; deeper oracle coverage remains an ongoing need. | Easy–Medium |

### 2.4 Structural observations

- `executor.py` is 1,135 lines and its `check_family()` is a large chain of
  family-specific branches. Prompt definitions are better separated into
  `cases.py`, but oracles, extraction, language heuristics, runtime dispatch,
  record creation, and output persistence still share one module.
- All manifests use a common broad shape and can express `execution.type`,
  `requires`, `timeouts`, `network`, `filesystem`, `variants`, generator
  parameters, and scoring weights. However, oracle behavior is mostly
  hard-coded in the executor; manifests document oracle descriptions but do
  not define an extensible oracle implementation.
- Most per-family `execution_seconds` declarations are 30s (with explicit
  60/120s exceptions), and all generation budgets are 120s. The executor has
  its own timeout arguments in branches, so adding task kinds risks drift
  unless the implementation reads and enforces manifest budgets consistently.
- Oracle reliability risks include substring checks for H1/H2, lexical
  checks for frontend/framework/config outputs, and English/Spanish/Arabic/
  Portuguese ratio thresholds. These are simple and deterministic, but can
  over-accept irrelevant matches or under-accept valid wording.
- H5 waits 0.25 seconds and constrains `wait_time()` to `<= 0.2`; that timing
  assertion may be sensitive to process scheduling and sandbox overhead.
- T9's separate calibration set is valuable, but no automated test currently
  binds its positive/negative labels to `check_family("T9", ...)`.
- `code-bench-25/SKILL.md`, test names/comments, and pack headings retain
  “25” while the manifests and `FAMILY_IDS` contain 29 families. Versioning
  also needs careful wording: original frozen prompts remain v1 while added
  tasks are marked v2.

## Phase 3 — Development plan

### 3.1 Design principles

1. Prefer executable, deterministic oracles with explicit fixtures and
   independent expected outcomes; use lexical checks only for intrinsically
   textual protocols, with adversarial false-positive tests.
2. Separate task prompt, fixture/generator, oracle, and resource policy, and
   make the manifest the enforceable source of timeouts and requirements.
3. Every added family should include a canonical case plus reproducible
   perturbed or adversarial instances wherever the task semantics support
   them.
4. Keep security tasks synthetic and non-deployable; run all generated code
   inside the existing fail-closed sandbox and do not require live services.
5. Gate releases on per-family golden positives and negatives, schema/raw
   record compatibility, deterministic seeds, and unchanged existing-suite
   pass rates.

### 3.2 Proposed new task families

The IDs below are proposals; confirm the naming/versioning scheme before
implementation. The set intentionally contains seven families.

| ID & name | Skill; language(s) | Description | Oracle | Why it matters | Effort | Dependencies |
|---|---|---|---|---|---|---|
| T30 — Injection-Resistant Query Repair | Secure SQL; Python + SQLite | Repair a small data-access helper that builds a query unsafely, preserving required filters while handling hostile-looking input as data. Include positive and injection-shaped negative fixtures. | Execute against isolated in-memory SQLite fixtures and assert exact rows plus unchanged database state. | Measures secure input handling, a critical production behavior missing from current SQL tasks. | Medium | New synthetic fixtures; reuse SQLite; add adversarial variant support and verify read-only expectations. |
| T31 — Algorithmic Complexity Repair | Algorithm design; Python | Replace a correct-but-quadratic solution with a scalable implementation, preserving edge-case behavior across generated inputs of increasing size. | Property checks against a reference oracle plus bounded operation-count or scaling ratio; avoid brittle wall-clock-only thresholds. | Tests whether agents optimize beyond toy correctness cases. | Hard | Instrumentation or controlled scaling harness; resource/time accounting; generated input seeds. |
| T32 — Multi-File Repository Feature | Repository reasoning; Python | Implement a small feature across a module, tests, and configuration/API boundary in a prebuilt synthetic repository, with regression tests. | Run repository test command in sandbox; verify required changed behavior and existing tests. | Represents the normal agent workflow of inspecting and modifying a codebase. | Hard | Workspace bundle/multi-file sandbox mount, fixture lifecycle, test-command allowlist, bounded output/runtime. |
| T33 — Resilient API Client | Error handling; Python or JavaScript | Complete a client wrapper for a deterministic local mock that returns success, transient failure, malformed response, and terminal failure. Require bounded retries, cleanup, and useful errors. | Local mock server or injected fake transport; assert outputs, retry counts, and error classes. | Tests reliable integration behavior not captured by R5's lexical checks. | Medium | Mock transport/service fixture; retry-aware deterministic oracle; no external network. |
| T34 — Concurrent Shared-State Safety | Concurrency; Python `asyncio` or threads | Repair a shared counter/queue or async fan-out function under concurrent inputs, including cancellation or one failed worker. | Deterministic barrier-controlled concurrency tests with invariants; no sleep-based race oracle. | Extends A16/H5 beyond single happy-path scheduling and sequential token refill. | Medium–Hard | Concurrency fixtures, bounded workers, cancellation-safe sandbox policy. |
| T35 — Type-System Error Diagnosis | Type systems; TypeScript and/or Rust | Diagnose and repair a task with generic/type inference or ownership errors while preserving behavior and a public signature. | Strict compiler plus runtime/reference tests where practical. | Current R1/R11 are simple compile exercises and do not measure repair of realistic compiler diagnostics. | Medium | Capture compiler output; language-specific fixtures; pinned compiler availability/versions. |
| T36 — Safe Migration and Query Plan | Database engineering; SQLite | Add a schema migration and query that preserve old data, handle duplicate/null edge cases, and meet a plan/invariant requirement. | Run migration and query against seeded in-memory DB; assert schema/data invariants and query result. | Broadens SQL beyond selecting rows and measures data-preserving changes. | Medium | Migration fixture runner and manifest fields for setup/teardown; SQLite is sufficient for initial version. |

### 3.3 Enhancements to existing tasks

| Existing task(s) | Proposed enhancement | Effort |
|---|---|---|
| T2, T3, T4, H4, H6 | Add seeded boundary and property-generated cases, including negative inputs and Unicode/empty cases where applicable; preserve existing canonical prompts. | Medium |
| T5, T6, T9, T10 | Add language-appropriate positive/negative calibration sets and direct oracle tests; separate language detection from semantic correctness and validate threshold behavior. | Medium |
| R2, R12 | Add joins, empty results, duplicate values, null handling, and at least one safe parameterized-query task; keep services local. | Medium |
| R3, R7, R8 | Replace selected substring checks with parsers or controlled protocol validation, while retaining intentionally byte-exact requirements only where the protocol requires them. | Medium |
| R4, R13 | Parse JSON and Dockerfile syntax/structure rather than searching broad substrings; add semantically wrong but token-complete negative cases. | Medium |
| R5, R9, R10, R11 | Add a local mocked runtime/build oracle for behavior, interactions, or type failures rather than shape-only checks. | Medium–Hard |
| H3 | Keep the existing seeded three-variant model as a template and define whether future families contribute canonical/perturbed/novel variants consistently. | Easy–Medium |
| H5, A16 | Add deterministic clock/barrier injection and failure/cancellation cases; avoid wall-clock race assertions. | Medium |

### 3.4 Executor and infrastructure changes needed

1. **Manifest-enforced runtime policy:** Pass manifest execution budgets and
   declared requirements to the executor; reject unknown/unsupported
   capabilities explicitly. Add optional memory, CPU, output, worker, and
   generated-input limits only for tasks that need them.
2. **Oracle registry or small typed oracle modules:** Move family behavior out
   of the central conditional chain behind explicit oracle functions while
   preserving current result contracts. Do not create a generic plugin system
   unless new task kinds demonstrate the need.
3. **Multi-file fixtures:** Support a read-only fixture tree plus a dedicated
   writable working copy in the sandbox, with path-safe setup and bounded
   test-command execution.
4. **Performance measurement:** Add deterministic operation counters or
   multiple-input scaling first; treat wall time and memory as separately
   reported signals with calibrated tolerances, not simplistic pass/fail
   thresholds.
5. **Mocked integrations:** Provide in-process or local-only fake services and
   injectable transports; do not enable external network egress.
6. **Variant/calibration tests:** Add a common fixture format for expected
   pass/fail answers and test each fixture against its live oracle. Enforce
   seed determinism and assert that generated prompts do not leak answers.
7. **Scoring compatibility:** Define when a task has checkpoints and partial
   credit. Current executor records one binary score; any new partial score
   must emit validated checkpoint evidence and preserve strict-pass semantics.
8. **Timeout and status semantics:** Distinguish missing tool/service,
   invalid response, wrong answer, sandbox failure, and timeout. Avoid
   converting arbitrary oracle exceptions to a status indistinguishable from
   missing infrastructure without retaining an actionable error reason.

### 3.5 Implementation priority and timeline

| Sprint | Focus | Tasks included | Estimated effort |
|---|---|---|---|
| Sprint 1 — Quick wins | Close fixture/oracle and documentation gaps without broad executor changes. | T9 calibration regression; add golden positive/negative replies for existing canonical families; refresh 25/29 naming and prompt-pack/version description; harden static oracles for R4/R13 with parsers. | 1–2 weeks |
| Sprint 2 — Core expansion | Security, database, and resilience tasks using existing local backends. | T30 injection-resistant query repair; T33 resilient API client; T36 safe migration/query plan; expand T2/T3/R2/R5 fixtures and variants. | 2–4 weeks |
| Sprint 3 — Advanced | Infrastructure-backed repository, complexity, concurrency, and compiler-diagnostic tasks. | T31 complexity repair; T32 multi-file repository feature; T34 concurrent shared-state safety; T35 type-system diagnosis; implement workspace, metrics, and manifest policy support. | 4–8 weeks |

Sprint effort is a planning estimate, not a commitment; infrastructure work
should be spiked and sized before scheduling.

### 3.6 Success metrics

- Keep a canonical inventory; the audit baseline was **29 families** and
  Sprint 2 raises it to **32**. Accurately count future additions; do not
  infer family count from the historic “25” suite name.
- The roadmap proposed **7 new families** to reach at least **14 skill
  dimensions**. The approved Sprint 2 scope completed T30, T33, and T36;
  T31, T32, T34, and T35 remain deferred, including repository-scale,
  performance, and concurrency coverage.
- Every new family has deterministic golden positive and negative cases;
  generated variants are reproducible from recorded seeds.
- Every family’s calibration fixtures are exercised against its production
  oracle in CI.
- Preserve current family results and raw-record schema; demonstrate **no
  regression in existing canonical pass rates** using a fixed local/stubbed
  baseline, and separately report live-model variance rather than hiding it.
- Keep sandbox isolation fail-closed; verify that new tests do not require
  external services or network access.
- Record execution latency and applicable resource metrics with explicit
  semantics; do not claim performance coverage unless measured and gated.
- Ensure suite docs, manifests, tests, runner family counts, and prompt-pack
  version documentation agree.

## Original approval boundary

This document began as an audit and plan. The implementation boundary below
records the approved Sprint 2 scope and supersedes the original read-only
status.

## Sprint 2 implementation status

The approved Sprint 2 mandate is complete:

| Work item | Status | Implementation |
|---|---|---|
| T30 — Injection-resistant query repair | Complete | Parameterized-query candidates execute against in-memory SQLite in the network-isolated Docker sandbox; tautology and destructive-looking inputs are checked against exact results and table integrity. |
| T33 — Resilient API client | Complete | An injected in-process transport exercises 503→200 retry/backoff and 404 fail-fast outcomes in the Docker sandbox, including attempt counts and structured errors. |
| T36 — Safe migration and query | Complete | In-memory SQLite checks the added column's type/default/nullability, existing row preservation, and ordered query result inside the Docker sandbox. |
| T2, T3, R2, R5 variants | Complete | Fixed perturbed prompts, deterministic oracles, canonical/negative fixtures, manifest declarations, and runner dispatch are present. R5 uses a Docker-isolated Node harness with an injected fluent mock client. |
| Manifest, documentation, and golden coverage | Complete | The inventory now has 32 families; all new families have positive and negative golden cases. |

### Lessons and scope notes

- Injecting transports and database connections keeps integration cases
  deterministic and avoids opening network access, even to local mock
  services. All generated Python and JavaScript in these new execution oracles
  runs through the shared fail-closed Docker sandbox.
- The Sprint 2 mandate selected three of the proposed new families (T30,
  T33, and T36). T31, T32, T34, and T35 remain future work; they are not
  reported as completed by this sprint.
- Existing-task variants use the established `perturbed` variant class and
  fixed prompts, rather than adding separate task-family IDs or a new
  generator format. This keeps family count at 32 and avoids a broad runner
  or manifest-schema refactor.
