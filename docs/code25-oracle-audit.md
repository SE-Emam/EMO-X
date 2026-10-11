# Code25 Oracle Audit — Initial Family Map

**Scope:** implementation/oracle review before real-model trials. The current suite contains 36 family manifests. This map records the primary verification mechanism and the next engineering risk to review; it does not claim every family has passed a full adversarial audit.

## Evidence inventory and limits

**Current status: UNIT-VERIFIED for the listed deterministic tests; not LIVE-EVALUATED.**

- `tests/generators/test_all_families_golden.py::test_every_family_has_canonical_golden_pass_and_fail` checks that the 36 `GOLDEN_REPLIES` IDs match the executor's 36 family IDs, and that every canonical positive/negative golden produces the expected result. Its `GoldenBackend` patches sandbox execution, so this is not proof that every real Docker/compiler/database runtime is available or works end-to-end.
- `tests/backends/test_manifest_truth.py` checks the 36-family inventory, prompt byte identity, manifest oracle/timeouts/forbidden-path metadata, and manifest IDs versus filenames.
- Family-specific deterministic tests strengthen the generic goldens where risk warrants it: A16 marker-complete wrong-runtime rejection; R4/R13 semantic/configuration negatives; T30 SQL injection and table preservation; T33 retry/backoff/exhaustion/permanent errors; T36 migration and data preservation; T37 dialect and contradiction guards. H1/H2/H3 and R11 have dedicated regressions for known false-positive/infrastructure-classification defects.
- The family map below records known limits and next risks; a row is not marked "fully audited" just because the generic golden passes. Static/lexical checks remain limited by their stated contracts.
- Real model/provider runs and official baseline construction are intentionally deferred. Historical Code25 bundles cover the earlier 25-family set only and are not evidence for all 36 current families.

## Family-by-family map

| Family | Primary verification path | Main risk / next review |
|---|---|---|
| A16 | Executable Python/async checks | Marker-complete wrong-runtime negative now proves that gather/fetch markers cannot replace the required [2, 4] runtime result; cancellation/error paths remain outside the current task contract. |
| H1 | Final numeric token must be 126 (v1.1) | Fixed substring false positive: mentioning 126 while giving 127 no longer passes. |
| H2 | Exact set of four nonnegative solution pairs (v1.1) | Fixed number-only false positive: wrong pairings containing 0, 27, 36, 45 no longer pass. |
| H3 | Final labeled numeric remainder (v1.2) | Fixed substring false positive: mentioning remainder 4 before a contradictory final answer no longer passes. |
| H4 | Sandboxed Python execution on palindrome edge cases | Add more Unicode and long-input cases only if they remain in the task contract. |
| H5 | Sandboxed token-bucket timing/capacity checks | Timing tolerance and flaky wall-clock boundaries need careful review. |
| H6 | Sandboxed first-occurrence search checks | Include duplicate, absent, and boundary indices in positive/negative coverage. |
| R1 | Rust compilation and executable primality checks | Compiler absence must be infrastructure status, not a model failure. |
| R2 | SQLite execution and data-preservation assertions | Add malformed/missing-table and transaction rollback cases if contract-relevant. |
| R3 | Required Git command/operation markers | Textual command presence may not prove commands are valid or correctly ordered. |
| R4 | JSON parsing and schema assertions | Ensure invalid JSON is rejected and unrelated keys do not mask wrong values. |
| R5 | Supabase client API/behavior markers | Static API-name checks may accept code that does not compile or enforce project scope. |
| R6 | Patch application plus resulting file checks | Include overlapping/conflicting patch and path traversal negatives. |
| R7 | Byte-exact tool-call/output check | Verify whitespace and encoding edge cases match the frozen contract. |
| R8 | Conventional-commit format and required authorization term | Lexical checks may accept a correctly shaped but semantically unrelated message. |
| R9 | HTML/CSS structural markers | Static markup checks do not establish browser rendering or accessibility. |
| R10 | React hook/event/export markers | Static checks do not establish a compilable or correctly functioning component. |
| R11 | Strict TypeScript compilation in the sandbox | Missing `tsc` now maps to `ERROR` infrastructure status (not a model failure); compiler diagnostics remain task failures. A regression test covers this distinction. |
| R12 | PostgreSQL query execution and result assertions | Unavailable PostgreSQL must remain an infrastructure status; add NULL/empty-row cases where required. |
| R13 | Parsed Dockerfile instruction/ordering checks | Structural validation is not a real Docker build or image security scan. |
| T2 | Sandboxed Fibonacci implementation tests | Check base cases, invalid inputs, and large values against the task contract. |
| T3 | Sandboxed bug-fix regression assertions | Add a negative case that reproduces the original bug, not only a happy-path result. |
| T4 | JavaScript runtime assertions | Confirm the test exercises behavior rather than only syntax or a printed marker. |
| T5 | Arabic/semantic marker checks | Lexical/ratio checks cannot prove a correct explanation; document that scope and test negation. |
| T6 | Sandboxed Python execution plus Arabic-language checks | Ensure code correctness and language checks fail independently for the intended reasons. |
| T7 | JSON structure/key/type checks | Adversarially test correct-looking keys with incorrect values or nested placement. |
| T8 | Sandboxed stdout/result and import restrictions | Test misleading printed output and forbidden-import attempts. |
| T9 | Spanish concept/marker checks | Lexical checks can be gamed with contradictory explanations; add marker-complete wrong cases. |
| T10 | Portuguese language/concept markers | Same limitation as other lexical language oracles; add adversarial semantic negatives. |
| T30 | Sandboxed SQLite SQL-injection behavior | Existing execution check is stronger than substring matching; retain injection and normal-input cases. |
| T31 | Algorithm/runtime complexity assertions | Ensure the input sizes distinguish intended complexity classes and avoid timing flakiness. |
| T32 | Multi-file repository task plus test execution | Test partial patches and cross-file inconsistencies, not just one successful repository state. |
| T33 | Injected HTTP transport; retries and backoff (v1.1) | Now checks 503→503→200, exhaustion at attempt 3, 0.1/0.2 delays, and fail-fast 404. |
| T34 | Sandboxed async/locking behavior | Exercise concurrency and cancellation paths without depending on nondeterministic timing. |
| T36 | SQLite migration execution and data preservation | Include repeated migration and rollback cases if idempotency/atomicity are part of the contract. |
| T37 | Dialect markers plus explicit negation and closure-lifetime contradiction guards (v1.2) | Return/termination paraphrases are covered; not a general semantic or native-speaker dialect evaluator. |

## Oracle classes

- **Execution-backed:** A16, H4–H6, R1, R2, R4, R6, R12, T2–T4, T6–T8, T30–T34, T36.
- **Primarily lexical/structural or answer-extraction:** H1–H3, R3, R5, R7–R11, R13, T5, T9, T10, T37.
- These categories describe implementation strategy, not a blanket quality rating. Every family still needs positive/negative oracle tests appropriate to its contract.

## Findings addressed in this PR

1. **H1 false positive:** substring presence of `126` allowed a response to mention 126 and then give 127. The oracle now checks the final numeric token; manifest v1.1.
2. **H2 false positive:** checking for four numbers allowed wrong pairings to pass. The oracle now compares the exact set of solution pairs; manifest v1.1.
3. **H3 contradiction false positive:** a correct `remainder is 4` substring overrode a different final answer. The oracle now validates the final labeled numeric result; manifest v1.2.
4. Golden negative cases are marker-complete: H1 mentions 126 but ends at 127; H2 includes all four numbers in incorrect pairs; H3 mentions remainder 4 before a contradictory final answer.

## Remaining work

- Continue adversarial positive/negative review of all 36 families, prioritizing remaining lexical/structural checks and R13. H3 contradiction handling and R11 missing-compiler classification now have regression coverage.
- Add focused regression tests with each fix; version any changed oracle contract.
- Keep historical bundles, frozen prompts, and score weights unchanged.
- Live model evaluation and baseline construction remain a separate, later phase.
