# Terms of Use — EMO-X Benchmark Numbers

EMO-X is an Apache-2.0 open-source project (owner: SE-Emam). The code is
free to use under the license; **published benchmark numbers** carry extra
rules so that results stay comparable and honest. If you cite an EMO-X
number, you accept these terms.

## 1. Sealed-bundle citation rule

Cite only sealed raw bundles (`results/raw/<RUN-ID>/` with a valid
`seal.json` per `shared/seal.py::verify_bundle_seal`). A citation must
reference the bundle's `RUN-ID` (and, where available, the derived
`provenance.json`) so anyone can re-verify hashes and regenerate derived
scores from raw. Numbers without a verifiable bundle are not citable as
EMO-X results.

## 2. No cherry-picking

Report the full run as scored by the harness: every suite, trial, and
instance in the bundle counts. You must not drop failing trials, failing
instances, or inconvenient suites to improve a headline number. Partial or
subset views must be labeled as such (subset name, trial count, seed) and
must never be presented as the official figure. Single-trial runs are
`PILOT`, never `OFFICIAL BASELINE` (SPEC B59).

## 3. Harness-change disclosure

Any change to prompts, oracles, scoring, task sets, sampling parameters,
seeds, or harness code between compared runs must be disclosed alongside
the numbers, including the `PROMPT_PACK` version, harness git SHA,
`prompt_sha256`/`harness_sha256` from the run manifest, and the
`comparison_key` comparability verdict (SPEC B58). Runs whose manifests
differ on frozen dimensions are not directly comparable — say so.

## 4. Scope-approval disclosure

Results run outside the approved evaluation scope (for example: modified
or unapproved harnesses, unreviewed forks, extra tooling, human
intervention mid-episode, or non-standard execution environments) must
disclose the deviation and must not be labeled `OFFICIAL BASELINE`.
Approval status (`claim_tier` in the run manifest, where present) must be
quoted verbatim, and any scope limitation must appear next to the number,
not in a footnote.

Violations may lead to a request for correction or retraction of the
cited numbers.
