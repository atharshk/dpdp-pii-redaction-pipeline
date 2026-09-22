# DPDP-Compliant PII Redaction Pipeline for RAG

A pipeline that detects and redacts PII from text before vector-database
ingestion — built around the actual engineering problem: **naive redaction
degrades retrieval.** Replacing every name with `[REDACTED]` collapses
distinct entities into the same token and destroys the semantic structure a
RAG system relies on. The design question this project answers is how to
remove PII while preserving enough structure for retrieval to still work.

This is a work in progress, built session by session. This document is
updated as each stage lands.

## Status: Session 1 — structured detection

Implemented so far: **Stage 2's regex layer** — detection of structured,
format-defined Indian PII, before any NER/unstructured detection is added.

- Email
- Phone (Indian mobile formats)
- PAN (with holder-type structural validation)
- Aadhaar-format numbers (with Verhoeff checksum validation)

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

### Known limitations (Session 1 scope)

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
- **No unstructured detection yet** (names, addresses, organisations) —
  that's Session 2, via Presidio/spaCy NER.
- **No overlap resolution, transformation strategy, or audit logging yet**
  — Stages 3-5 of the pipeline land in later sessions.
- **No real-world evaluation yet** — the labeled test set and
  precision/recall/F1 numbers are Session 3-4.

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
tests/
  fixtures.py               # synthetic Aadhaar-number generator
  test_*.py
scripts/
  demo.py                   # run all detectors on a sample document
```

## Running

```bash
python -m venv .venv
.venv/Scripts/activate        # or source .venv/bin/activate on Linux/Mac
pip install -e . pytest
pytest
python scripts/demo.py
```

## Scope disclaimer

This is a portfolio/reference engineering project, not a certified or
production-hardened compliance product. It is not a substitute for a formal
DPIA, legal review, or a production security assessment.
