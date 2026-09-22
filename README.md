# DPDP-Compliant PII Redaction Pipeline for RAG

A pipeline that detects and redacts PII from text before vector-database
ingestion — built around the actual engineering problem: **naive redaction
degrades retrieval.** Replacing every name with `[REDACTED]` collapses
distinct entities into the same token and destroys the semantic structure a
RAG system relies on. The design question this project answers is how to
remove PII while preserving enough structure for retrieval to still work.

This is a work in progress, built session by session. This document is
updated as each stage lands.

## Status: Session 2 — unstructured (NER) detection

Session 1 built **Stage 2's regex layer** — structured, format-defined
Indian PII. Session 2 adds the other half of Stage 2: **unstructured
detection** via Presidio (spaCy `en_core_web_lg`-backed) for person names
and locations.

- Email
- Phone (Indian mobile formats)
- PAN (with holder-type structural validation)
- Aadhaar-format numbers (with Verhoeff checksum validation)
- Person names, locations (Presidio NER, `en_core_web_lg`)

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

### Known limitations (Session 1-2 scope)

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
- **No overlap resolution yet between the regex and NER layers** (Stage 3)
  — if both layers fire on the same span, nothing merges or arbitrates them
  yet. That's the next piece of work.
- **No transformation strategy or audit logging yet** — Stages 4-5 land in
  later sessions.
- **No real-world evaluation yet** — the labeled test set and
  precision/recall/F1 numbers, including actual (not anecdotal) recall on
  Indian names, are Session 3-4.

All test data (including every Aadhaar-format number in this repo) is
synthetic: generated programmatically with a valid Verhoeff checksum but not
a real, issued identifier. See [`tests/fixtures.py`](tests/fixtures.py).

## Project layout

```
src/pii_redaction/
  entity.py               # PIIEntity — the shared span type every detector emits
  detectors/
    verhoeff.py            # Verhoeff checksum (validate + generate)
    email.py
    phone.py
    pan.py
    aadhaar.py              # AadhaarDetector (checksum-validated) + AadhaarNaiveDetector (comparison only)
    ner.py                  # PresidioNERDetector — PERSON/LOCATION
tests/
  fixtures.py               # synthetic Aadhaar-number generator
  test_*.py
scripts/
  demo.py                   # run all detectors on a sample document
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
```

## Scope disclaimer

This is a portfolio/reference engineering project, not a certified or
production-hardened compliance product. It is not a substitute for a formal
DPIA, legal review, or a production security assessment.
