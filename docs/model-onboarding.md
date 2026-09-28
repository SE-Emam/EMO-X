# Model onboarding checklist (capability gating)

Every model runs only the suites it is capable of. Scored zeros from
an incapable model are inadmissible — the harness refuses BEFORE the
first model call instead.

## 1. Declare modalities

```
--model-modalities text[,vision][,embeddings][,audio]
```

- Chat/coding models: `text` (default; omit the flag).
- Vision-language models: `text,vision`.
- Embedding-only models: `embeddings` — runnable on NO current suite
  (all suites need text except `vision`, which needs vision). The run
  is refused with `ModelCapabilityDenied`, never scored 0%.
- Unknown tokens are rejected (`ValueError`, fail closed).

## 2. Match suites

| Suite family | Required modality |
|---|---|
| everything except vision | `text` |
| `vision` (V1–V6) | `vision` (plus the live image-probe gate) |

## 3. Trial, then baseline

1. `--self-test` green.
2. One trial on one family (`--only`, `--trials 1`) to validate the
   backend route (auth, latency, rate limits).
3. Full run: `--trials 3 --seed 0`; verify the manifest carries your
   `model_modalities`; check seal + R3 gates.
4. New model family (e.g. a new release)? Open an issue first: declare
   modalities, provider route, and license/training-data terms.

## 4. Rules that never bend

- The declaration is recorded in `manifest.json`
  (`model_modalities`) and travels with the sealed bundle.
- Misdeclaration (claiming `text` for an embedding model) produces
  garbage scores that fail review — and the manifest proves it.
- Hidden suites never run on third-party models, regardless of
  modalities.
