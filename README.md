# DPDP-Compliant PII Redaction Pipeline for RAG

A pipeline that detects and redacts PII from text before vector-database
ingestion — built around the actual engineering problem: **naive redaction
degrades retrieval.** Replacing every name with `[REDACTED]` collapses
distinct entities into the same token and destroys the semantic structure a
RAG system relies on. The design question this project answers is how to
remove PII while preserving enough structure for retrieval to still work.

This is a work in progress, built session by session. This document is
updated as each stage lands.

## Status: Session 3 — labeled test set + redaction pipeline (Stages 3-4)

Session 1 built **Stage 2's regex layer** (structured Indian PII). Session 2
added the other half of Stage 2: **unstructured detection** via Presidio for
person names and locations. Session 3 adds the pieces that turn "detection"
into an actual redaction pipeline: **Stage 3 (resolution)**, **Stage 4
(transformation)**, and a **134-case labeled test set** to evaluate against
in Session 4.

- Email
- Phone (Indian mobile formats)
- PAN (with holder-type structural validation)
- Aadhaar-format numbers (with Verhoeff checksum validation)
- Person names, locations (Presidio NER, `en_core_web_lg`)
- Overlap resolution between the regex and NER layers (Stage 3)
- Per-entity-type redaction, including consistent pseudonymisation for
  person names (Stage 4)
- A 134-case labeled test set covering all of the above, plus negatives and
  near-misses (used for eval starting Session 4)

### Why checksum validation matters for Aadhaar

Aadhaar numbers are 12 digits with a trailing Verhoeff check digit. A bare
`\d{12}` regex fires on order numbers, tracking IDs, and other incidental
12-digit strings in real documents. Validating the Verhoeff checksum turns a
low-precision format match into a high-precision identifier match.

Run `python scripts/demo.py` to see this on a sample document: the naive
12-digit detector scores **0.33 precision** (1 real Aadhaar number out of 3
matches — the other two are an order number and a tracking ID), while the
checksum-validated detector scores **1.00** on the same input. This is a
demonstration on a small illustrative sample, not a claim about production
precision — that number comes from the labeled evaluation in a later
session.

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

The real, measured per-category recall — including whatever gap shows up
between Indian and Western names at scale — comes from the labeled test set
in Session 3-4, not from this script.

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

Run `python scripts/demo.py` to see the full pipeline (`pipeline.redact_document()`)
on a sample document, including the audit log and a concrete instance of
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

### Known limitations (Session 1-3 scope)

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
- **No persisted/formal audit logging yet.** `RedactionRecord`s are
  returned in-memory from `redact()`; writing them to a durable audit trail
  (and the ISO-27001-flavoured framing of that) is Session 5 polish.
- **No Stage 1 normalisation yet** (Unicode/whitespace cleanup) — the
  pipeline currently assumes reasonably clean input text.
- **No real-world evaluation yet** — the labeled test set exists (134
  cases) but no precision/recall/F1 has been computed against it. That,
  including actual (not anecdotal) recall on Indian names and the
  strict-vs-relaxed matching-rule decision, is Session 4.
- **The test set was built by the same person building the detectors.**
  Named directly rather than glossed over: this is a real methodological
  limitation (see Session 4 "Threats to Validity" once the eval lands),
  mitigated only by writing the test set before tuning anything further and
  by the build-time sanity check already surfacing genuine detector misses
  rather than a suspiciously clean pass.

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
  pipeline.py                # glues detectors -> resolution -> transform together
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
```

## Scope disclaimer

This is a portfolio/reference engineering project, not a certified or
production-hardened compliance product. It is not a substitute for a formal
DPIA, legal review, or a production security assessment.
