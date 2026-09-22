# DPDP-Compliant PII Redaction Pipeline for RAG

A pipeline that detects and redacts PII from text before vector-database
ingestion — built around the actual engineering problem: **naive redaction
degrades retrieval.** Replacing every name with `[REDACTED]` collapses
distinct entities into the same token and destroys the semantic structure a
RAG system relies on. The design question this project answers is how to
remove PII while preserving enough structure for retrieval to still work.

This is a work in progress, built session by session. This document is
updated as each stage lands.

## What this project actually adds beyond calling Presidio

Presidio already detects PII. Calling `AnalyzerEngine().analyze()` is not
this project. What's actually built here, concretely:

1. **Indian-format structured detection Presidio doesn't ship.** PAN and
   Aadhaar-format numbers aren't in Presidio's default recognizer set at
   all. Aadhaar detection includes a real Verhoeff checksum implementation
   (see [`verhoeff.py`](src/pii_redaction/detectors/verhoeff.py)), not just
   a 12-digit regex — see "Evaluation results" for the measured precision
   difference that makes.
2. **The retrieval-preservation framing and the strategy table that
   implements it.** Presidio redacts or anonymizes; it doesn't decide that
   person names should get *consistent* pseudonyms so a RAG system can
   still tell two people apart, or that a bare city name should be
   retained rather than blanked because it's already at the coarse end of
   a street→city hierarchy. That table, and the reasoning behind each row,
   is in "Stage 4" below.
3. **Explicit overlap resolution between detector layers**, with a
   documented precedence rule — see "Stage 3" below. Presidio has its own
   internal conflict resolution for recognizers it manages; this project's
   resolution logic sits a layer above that, arbitrating between Presidio's
   NER output and independently-built regex/checksum detectors.
4. **A measured evaluation on an India-specific labeled test set**, not
   Presidio's own test suite. See "Evaluation results" below.
5. **An audit trail designed for compliance evidence** — offsets, entity
   type, strategy, confidence, persisted as append-only JSONL — that
   deliberately never stores the PII it's logging the redaction of. See
   "Stage 4" and [`audit_log.py`](src/pii_redaction/audit_log.py).

**Why Presidio/spaCy at all, rather than building NER from scratch:**
because reimplementing a named-entity recognizer is a multi-month research
problem with worse baseline accuracy than a maintained, widely-used library
gets out of the box. The judgment call that *is* this project's own is
knowing where Presidio's defaults are wrong for this use case (its
Indian-format coverage, its blanket redaction strategy) and building
exactly those pieces — not the parts a library already does well.

## Status: Session 5 — persisted audit logging, polish, published

Session 1 built **Stage 2's regex layer** (structured Indian PII). Session 2
added the other half of Stage 2: **unstructured detection** via Presidio for
person names and locations. Session 3 added **Stage 3 (resolution)**,
**Stage 4 (transformation)**, and a 134-case labeled test set. Session 4
ran the pipeline against that test set and reported real, measured
precision/recall/F1 — see [Evaluation results](#evaluation-results-session-4)
below and the full [`EVAL_RESULTS.md`](EVAL_RESULTS.md). Session 5 adds
**Stage 5's persisted audit trail** (append-only JSONL, never the original
PII text), consolidates the "what did you actually build" defense into one
place (immediately below), and publishes the repo.

- Email
- Phone (Indian mobile formats)
- PAN (with holder-type structural validation)
- Aadhaar-format numbers (with Verhoeff checksum validation)
- Person names, locations (Presidio NER, `en_core_web_lg`)
- Overlap resolution between the regex and NER layers (Stage 3)
- Per-entity-type redaction, including consistent pseudonymisation for
  person names (Stage 4)
- A 134-case labeled test set, and a measured evaluation harness against it
  (`src/pii_redaction/evaluation.py`, `scripts/evaluate.py`)

### Why checksum validation matters for Aadhaar

Aadhaar numbers are 12 digits with a trailing Verhoeff check digit. A bare
`\d{12}` regex fires on order numbers, tracking IDs, and other incidental
12-digit strings in real documents. Validating the Verhoeff checksum turns a
low-precision format match into a high-precision identifier match.

Run `python scripts/demo.py` to see this on a sample document: the naive
12-digit detector scores **0.33 precision** (1 real Aadhaar number out of 3
matches — the other two are an order number and a tracking ID), while the
checksum-validated detector scores **1.00** on the same input. That's a
demonstration on one small illustrative document, not the real evaluation.
The measured result is in "Evaluation results" below: on the full 134-case
labeled test set, the checksum-validated `AadhaarDetector` (the one
actually used in the pipeline) scores **1.000 precision and 1.000 recall**
— see there for why a perfect score on deterministic detectors is expected
and proves less than it looks like it does.

### PAN structural validation

PAN format is `AAAA` + holder-type letter + `A` + `9999` + `A`. The 4th
character is not a free letter — CBDT only issues 10 holder-type codes
(`A B C F G H J L P T`). Constraining that position is a real precision
improvement over `[A-Z]{5}\d{4}[A-Z]`, which accepts all 26 letters there.
The 10th character is also a check character, but its generation algorithm
is not public, so it is not validated here — noted as a limitation, not
silently ignored.

### Unstructured detection (Presidio NER)

`PresidioNERDetector` wraps Presidio's `AnalyzerEngine`, restricted to
`PERSON` and `LOCATION` — the entity types the regex layer structurally
cannot cover. `ORGANIZATION` is intentionally excluded (see Known
Limitations below for why). Structured PII stays on the regex detectors,
which have Indian-format and checksum precision Presidio's generic
recognizers don't; this detector is scoped to exactly what's left.

**Anecdotal spot-check, not a measured result:** `scripts/explore_indian_names.py`
runs the detector against a small hand-written set of sentences spanning
North Indian, South Indian, Muslim, Christian, and Sikh naming conventions,
plus names that are also common English words. Sample size is too small (12
sentences, hand-written) to be a recall claim — but it already surfaced a
concrete, reproducible failure worth naming here rather than saving for
Session 4:

- 11/12 matched exactly, including multi-word South Indian, Muslim, and
  Sikh names (`Venkataraman Subramaniam`, `Mohammed Irfan Khan`,
  `Gurpreet Singh`).
- The one miss: **"Hope Fernandez"** was only partially detected as
  `Fernandez` — the model dropped "Hope" from the span, almost certainly
  because it's also a common English noun. This is exactly the "names that
  are common words" failure mode called out as a real risk before any
  measurement was taken. It's a boundary/span error, not a total miss,
  which is itself relevant to the strict-vs-relaxed matching-rule decision
  Session 4 has to make explicit.

The real, measured per-category recall comes from the labeled test set, not
from this script — see "Evaluation results" below. (Spoiler: the measured
result doesn't match the "Indian vs Western" framing this paragraph
expected going in — see that section for what actually drives the gap.)

### Stage 3 — resolving overlapping spans

The regex detectors and the NER detector run independently and can, in
principle, both fire on the same characters. `resolution.resolve()` merges
them into one non-overlapping set with an explicit, documented precedence:

1. Structured, format/checksum-validated regex hits (email, phone, PAN,
   Aadhaar) outrank NER hits on the same characters — those detectors
   encode an explicit format rule (a checksum, a holder-type code) that NER
   has no equivalent for, so a structured hit is trusted over a generic one.
2. Within the same tier: higher confidence wins, then longer span, then
   earlier start offset (for deterministic output).

Implementation is greedy interval scheduling — sort by that priority,
accept a span only if it doesn't overlap something already accepted. This
is not the only reasonable design (an exact optimum could occasionally
accept two shorter high-priority spans instead of one longer one that
blocks both); the greedy version is documented as the trade-off actually
made, in [`resolution.py`](src/pii_redaction/resolution.py).

### Stage 4 — the transformation strategy table (the actual differentiator)

`transform.redact()` applies a different strategy per entity type, per the
architecture's own reasoning — not one blanket `[REDACTED]`:

| Entity type | Strategy | Why |
|---|---|---|
| Email, phone, PAN, Aadhaar | Fixed placeholder (e.g. `[EMAIL_REDACTED]`) | Zero retrieval value on their own, high re-identification risk |
| Person | **Consistent pseudonymisation** — every span with the same text (case-insensitive) maps to the same `PERSON_<letter>` token throughout the document | Preserves entity relationships ("PERSON_A's account" vs "PERSON_B's account") for retrieval, without revealing who either of them is |
| Location | Retained as-is | The detector only ever returns city/country-level spans (spaCy's `GPE`/`LOC`) — that's already the coarse end of a street→city coarsening strategy; there's no street-level address in scope to coarsen further, so redacting a bare city name would delete retrieval-useful context for negligible privacy gain |

Person pseudonymisation is **exact-string matching only** — there is no
coreference resolution. "Priya Sharma" and a later bare "Priya" are *not*
linked to the same token; each distinct string gets its own token the first
time it's seen. This is a real limitation (see below), not hidden.

Every redaction also produces a `RedactionRecord` — entity type, character
offsets, length, strategy applied, replacement, detector confidence. The
record **does not store the original PII text**, on purpose: an audit log
that keeps a plaintext copy of the exact thing it just redacted defeats the
point of redacting it. Offsets are enough for an auditor to correlate
against the source document under proper access control.

### Stage 5 — persisting the audit trail

`redact_document(text, audit_log_path=...)` optionally appends every
`RedactionRecord` from that call to a JSONL file — see
[`audit_log.py`](src/pii_redaction/audit_log.py). "Appends" is deliberate:
`write_audit_log()` opens in append mode by default, because a log an
application can silently overwrite isn't evidence of anything. An optional
`document_id` tags every line so records from different documents
processed into the same log file stay attributable — metadata about the
pipeline run, not PII, so it doesn't reintroduce the thing Stage 4 was
careful to keep out.

Run `python scripts/demo.py` to see the full pipeline
(`pipeline.redact_document()`) on a sample document, including a persisted
audit log written to `demo_audit_log.jsonl` and a concrete instance of
consistent pseudonymisation: "Priya Sharma" appears twice in the sample
text and both mentions resolve to the same `PERSON_A` token, while "Rahul
Verma" — a different person — gets the distinct `PERSON_B`.

### The labeled test set

`tests/data/cases.py` defines 134 hand-authored cases; `tests/data/build_labeled_set.py`
compiles them into [`tests/data/labeled_pii_test_set.jsonl`](tests/data/labeled_pii_test_set.jsonl).
Character offsets are **never hand-counted** — each case lists entity
substrings in reading order, and the build script locates them with
sequential string search, asserting the located text matches exactly and
that no two gold spans overlap. A hand-typed offset is exactly the kind of
unchecked claim this project's own ground rule forbids; this is the
alternative.

Coverage: 40 person names spanning North Indian, South Indian, Muslim,
Christian, and Sikh naming conventions, plus 8 names that are also common
English words; 8 emails; 10 phones (formatted/unformatted, `+91`, leading
`0`); 10 PANs (one per real CBDT holder-type code); 10 Aadhaar-format
numbers (valid Verhoeff checksum, grouped and ungrouped); 8 locations; 16
mixed multi-entity sentences; 14 true negatives (no PII at all); 12
near-miss negatives (12-digit order numbers/tracking IDs/timestamps with
invalid checksums, PAN-shaped strings with invalid holder codes, phone-shaped
numbers with an invalid leading digit — all asserted, not assumed, to fail
their respective validators); 6 organisation-only distractor sentences.

The build script also runs a build-time sanity check — each gold entity
against its own single-purpose detector — to catch *authoring* mistakes
before they'd show up as confusing Session 4 results. It is explicitly not
the Session 4 evaluation (no combined-pipeline metric, no matching-rule
decision exercised here). It already surfaced two real, reproducible
detector behaviors worth keeping on record now:

- **Common-word first names get dropped or lost entirely.** "Hope
  Fernandez" → only `Fernandez` detected. "Happy Singh" → only `Singh`.
  "Sunny Malhotra" → **nothing detected at all**, not even the surname.
  This is the "names that are common words" failure mode named as a risk
  before any measurement was taken — not a coincidence found after the
  fact.
- **Possessive `'s` gets absorbed into the PERSON span boundary.**
  `"Ayesha Siddiqui's Aadhaar..."` → detected span is `Ayesha Siddiqui's`,
  including the apostrophe-s, not `Ayesha Siddiqui`. This is a systematic
  tokenization artifact (spaCy includes the possessive clitic in the
  entity span), not a semantic miss — and it's exactly why Session 4 has to
  pick and document a strict-vs-relaxed span-matching rule before
  computing any precision/recall number, rather than after.

Two failure cases, reproducible in seconds, cited from the actual test set
— not invented for this README after the fact.

### Evaluation results (Session 4)

`scripts/evaluate.py` runs Stage 2 (detect) + Stage 3 (resolve) against all
134 test-set cases and reports real precision/recall/F1. Full output,
including every individual failure, is in [`EVAL_RESULTS.md`](EVAL_RESULTS.md)
— generated by that script, not hand-written. This section is that report's
numbers, not a paraphrase.

**Strict matching (primary, reported number):**

| Entity type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| AADHAAR | 14 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| EMAIL | 15 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| LOCATION | 17 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| PAN | 16 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| PERSON | 46 | 5 | 6 | 0.902 | 0.885 | 0.893 |
| PHONE | 18 | 0 | 0 | 1.000 | 1.000 | 1.000 |

**Why the structured detectors are all 1.000 — and why that number alone
proves less than it looks like it does:** email/phone/PAN/Aadhaar/location
are deterministic pattern or checksum matches against well-formed synthetic
inputs written to conform to the formats those detectors already target.
Perfect accuracy here mostly confirms the detectors are wired correctly
into the eval harness, not that they'd score 1.0 on messier real-world
text (a phone number split across a line break, a PAN with OCR noise, a
place name spaCy has never seen). Those detectors' actual edge-case
correctness was already exercised in Sessions 1-2's unit tests (invalid
PAN holder codes, corrupted Aadhaar checksums, non-mobile prefixes) — this
eval is testing integration, not re-proving detector correctness. The
genuinely informative number in this table is **PERSON**, because NER is
the one probabilistic component: 0.902 precision, 0.885 recall.

**The Indian-names hypothesis, and what actually happened:** going in, the
documented expectation (see Session 2) was that spaCy's Western-centric
training would show a recall gap on Indian names specifically. The
measured result **does not support that hypothesis** — reporting it exactly
that way rather than reaching for a Western/Indian narrative because it was
the anticipated one:

| Naming convention | Recall (strict) |
|---|---|
| person_christian | 1.000 |
| person_muslim | 1.000 |
| person_north_indian | 1.000 |
| person_sikh | 1.000 |
| person_south_indian | 1.000 |
| person_common_word_name | **0.625** |

Every regional/community naming convention tested — North Indian, South
Indian, Muslim, Christian, Sikh — hit **perfect recall**, including
multi-word names like "Venkataraman Subramaniam" and "Mohammed Irfan
Khan." The entire PERSON recall gap comes from one category: names that
are also common English words. That is a real, specific, more useful
finding than "Indian names underperform" would have been, because it
tells you exactly what to test for in production text, rather than
gesturing at an ethnicity-shaped gap that this data doesn't show.

**Relaxed matching (diagnostic, not the reported number)** shows *why*
strict PERSON recall is 0.885 and not higher: under relaxed matching,
PERSON recall rises to 0.981 with zero false positives. Two of the three
common-word-name misses ("Hope Fernandez" → `Fernandez`, "Happy Singh" →
`Singh`) and all three possessive-boundary cases ("Ayesha Siddiqui's" etc.)
turn into true positives under relaxed matching — they're boundary
artifacts, not total misses. Only **one** case remains a miss under any
matching rule: **"Sunny Malhotra" — the detector returns nothing at all**,
not even the surname. That is the strongest concrete failure case this
project has: reproduce it with
`PresidioNERDetector().detect("Sunny Malhotra confirmed the meeting for Tuesday.")`
and it returns an empty list.

**Two failure cases, memorized cold, for "show me a case where it fails":**
1. `"Sunny Malhotra confirmed the meeting for Tuesday."` → zero entities
   detected. Total miss, not a boundary error — "Sunny" as a common
   adjective/word appears to suppress detection of the whole name, not
   just itself.
2. `"Ayesha Siddiqui's Aadhaar ... were verified together."` → detected
   span is `Ayesha Siddiqui's`, including the possessive `'s`. A
   systematic tokenization artifact, reproducible on every possessive
   construction in the test set (3/3), not a one-off.

**Threats to validity, named directly rather than left for someone else to
raise:**

- **This test set was built by the same person who built the detectors.**
  No independent labeling, no third-party review. Mitigated only by:
  writing the test set's sentences before running any evaluation against
  it (Session 3, before this session), and by the fact that the build-time
  sanity check and this evaluation both surfaced real, unflattering
  failures rather than a suspiciously clean pass — a rigged test set would
  not have produced an 0.885 PERSON recall and a fully-missed name. What
  this does *not* rule out: unconscious bias in which sentences got
  written in the first place (e.g. avoiding genuinely hard cases without
  realizing it). An independent, third-party-labeled corpus is the real
  fix, and is out of scope for a solo portfolio project.
- **Sample size is small and hand-authored, not sampled from a real
  corpus.** 134 cases, ~50 PERSON mentions. The 100% regional recall
  numbers above are consistent with no gap on *this data*; they are not
  strong evidence of no gap in general — a larger, corpus-sampled test set
  could still surface one this test set is too small or too clean to catch.
- **LOCATION's 1.000 recall used well-known major Indian cities only**
  (Bangalore, Hyderabad, Chennai, ...). It says nothing about recall on
  smaller towns or place names that double as common words — a harder,
  more realistic LOCATION test is future work, not something this result
  covers.
- **This evaluates detection (Stage 2+3), not the full redacted output or
  retrieval quality.** No embedding-based retrieval comparison has been
  run — see Known Limitations.

### Known limitations (Session 1-5 scope)

- **Phone**: mobile numbers only (first digit 6-9, 10 digits, optional
  `+91`/`0` prefix). Landline numbers (STD code + local number) are not
  covered.
- **PAN**: the 10th-character check digit is not validated (no public
  algorithm to verify against); only the 4th-character holder-type code is
  structurally checked.
- **Aadhaar**: format + Verhoeff checksum only. This does not confirm a
  number is a *real, issued* Aadhaar number — only that it is
  checksum-consistent, which is the strongest signal available without a
  UIDAI lookup (which this project does not and should not perform).
- **NER scope**: only `PERSON` and `LOCATION` are extracted. `ORGANIZATION`
  is deliberately excluded — Presidio's own default config disables it
  ("Has many false positives" from spaCy's noisy `ORG` label), and the
  project's own transformation strategy (Stage 4) retains organisations
  rather than redacting them, so detecting them isn't safety-critical here.
  Presidio's spaCy recognizer also emits `NORP` (nationality/religious/
  political groups) and `DATE_TIME`; both are out of scope this session.
  `LOCATION` is whatever spaCy's `GPE`/`LOC` labels catch (cities,
  countries, named places) — it is not full postal-address parsing.
- **Person pseudonymisation has no coreference resolution.** Matching is
  exact-string (case-insensitive) only. "Priya Sharma" and a later bare
  "Priya" get *different* tokens, because nothing links them as referring
  to the same entity. Real coreference resolution is a separate, harder NLP
  problem, out of scope here.
- **No street-level address detection or coarsening.** `LOCATION` is
  whatever spaCy's `GPE`/`LOC` labels catch, not full postal addresses — so
  there's nothing finer to coarsen down to.
- **Audit log persistence has no rotation, encryption-at-rest, or access
  control of its own.** `write_audit_log()` appends plain JSONL to a local
  path — it's a building block for compliance evidence, not a hardened
  audit system. Those concerns belong to whatever deploys this (a real
  logging pipeline, a database with its own access controls), not to this
  function.
- **No Stage 1 normalisation yet** (Unicode/whitespace cleanup) — the
  pipeline currently assumes reasonably clean input text.
- **No embedding-based retrieval-quality evaluation.** The whole project is
  framed around preserving retrieval quality, but that claim is still
  unmeasured — no comparison of retrieval on redacted vs unredacted text
  has been run. See "Evaluation results" above for what *is* measured
  (detection precision/recall/F1) and what explicitly isn't.
- **The test set's methodological limitations** — same-author test set and
  detectors, small hand-authored sample size, an easy (major-cities-only)
  LOCATION slice — are detailed in "Threats to validity" above rather than
  repeated here.

All test data — every Aadhaar-format number and every PAN in this repo,
including the entire labeled test set — is synthetic: generated or
hand-invented to match the real format, never a real, issued identifier.
Aadhaar numbers carry a genuinely valid Verhoeff checksum, computed
programmatically. See [`tests/fixtures.py`](tests/fixtures.py) and
[`tests/data/cases.py`](tests/data/cases.py).

## Project layout

```
src/pii_redaction/
  entity.py               # PIIEntity — the shared span type every detector emits
  resolution.py            # Stage 3 — resolve overlapping spans across detectors
  transform.py              # Stage 4 — per-entity-type redaction + audit records
  pipeline.py                # glues detectors -> resolution -> transform (-> audit_log) together
  evaluation.py               # Session 4 — strict/relaxed matching, precision/recall/F1
  audit_log.py                # Stage 5 — persisted, append-only JSONL audit trail
  detectors/
    verhoeff.py            # Verhoeff checksum (validate + generate)
    email.py
    phone.py
    pan.py
    aadhaar.py              # AadhaarDetector (checksum-validated) + AadhaarNaiveDetector (comparison only)
    ner.py                  # PresidioNERDetector — PERSON/LOCATION
tests/
  fixtures.py               # synthetic Aadhaar-number generator
  data/
    cases.py                 # raw labeled test-set case definitions (synthetic)
    build_labeled_set.py       # computes offsets, validates, writes the JSONL
    labeled_pii_test_set.jsonl  # generated — 134 cases, do not hand-edit
  test_*.py
scripts/
  demo.py                   # run the full pipeline on a sample document
  explore_indian_names.py    # anecdotal NER spot-check, not a measured eval
  evaluate.py                 # runs the measured eval, writes EVAL_RESULTS.md
EVAL_RESULTS.md              # generated by scripts/evaluate.py — do not hand-edit
```

## Running

```bash
python -m venv .venv
.venv/Scripts/activate        # or source .venv/bin/activate on Linux/Mac
pip install -e . -r requirements.txt
python -m spacy download en_core_web_lg
pytest
python scripts/demo.py
python scripts/explore_indian_names.py
python tests/data/build_labeled_set.py   # regenerates labeled_pii_test_set.jsonl
python scripts/evaluate.py               # regenerates EVAL_RESULTS.md
```

## Scope disclaimer

This is a portfolio/reference engineering project, not a certified or
production-hardened compliance product. It is not a substitute for a formal
DPIA, legal review, or a production security assessment.
