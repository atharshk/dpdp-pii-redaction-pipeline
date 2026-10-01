# DPDP-Compliant PII Redaction Pipeline for RAG

[![tests](https://github.com/atharshk/dpdp-pii-redaction-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/atharshk/dpdp-pii-redaction-pipeline/actions/workflows/tests.yml)

A pipeline that detects and redacts PII from text before vector-database
ingestion — built around the actual engineering problem: **naive redaction
degrades retrieval.** Replacing every name with `[REDACTED]` collapses
distinct entities into the same token and destroys the semantic structure a
RAG system relies on. The design question this project answers is how to
remove PII while preserving enough structure for retrieval to still work.

## Evaluation results

Every number below is generated output, not hand-typed — [`EVAL_RESULTS.md`](EVAL_RESULTS.md)
and [`RETRIEVAL_RESULTS.md`](RETRIEVAL_RESULTS.md) are written directly by
`scripts/evaluate.py` and `scripts/evaluate_retrieval.py`. Measured against
spaCy model `en_core_web_lg==3.8.0` (pinned exactly in `requirements.txt`) —
these numbers are specific to that model version.

### Detection (134-case labeled test set)

Matching rule, decided before anything was measured: **strict** (exact
character-offset + type match) is the primary, reported metric. **Relaxed**
(any span overlap of the same type) is shown only as a diagnostic — never
as the headline number, since it would silently give full credit for
boundary slop.

| Entity type | Precision | Recall | F1 |
|---|---|---|---|
| AADHAAR | 1.000 | 1.000 | 1.000 |
| EMAIL | 1.000 | 1.000 | 1.000 |
| LOCATION | 1.000 | 1.000 | 1.000 |
| PAN | 1.000 | 1.000 | 1.000 |
| PERSON | 0.902 | 0.885 | 0.893 |
| PHONE | 1.000 | 1.000 | 1.000 |

**Why five of six rows are a perfect 1.000 — and why that proves less than
it looks like it does:** email/phone/PAN/Aadhaar/location are deterministic
pattern or checksum matches against well-formed synthetic input written to
conform to the formats those detectors already target. A perfect score here
mostly confirms the detectors are wired correctly into the eval harness,
not that they'd score 1.0 on messier real-world text (a phone number split
across a line break, a PAN with OCR noise, a place name spaCy has never
seen). Those detectors' actual edge-case correctness was already exercised
separately, in unit tests covering invalid PAN holder codes, corrupted
Aadhaar checksums, and non-mobile phone prefixes — this eval tests
integration, not detector correctness in isolation. **PERSON is the
genuinely informative row**, because NER is the one probabilistic
component: 0.902 precision, 0.885 recall.

**The hypothesis going in, stated before measuring, did not hold up:**
spaCy's training is Western-centric, so the expectation was a recall gap on
Indian names specifically. The measured result does not support that —
reported exactly that way rather than reached for after the fact:

| Naming convention | Recall (strict) |
|---|---|
| North Indian | 1.000 |
| South Indian | 1.000 |
| Muslim | 1.000 |
| Christian | 1.000 |
| Sikh | 1.000 |
| Names that are also common English words | **0.625** |

Every regional/community naming convention tested — including multi-word
names like "Venkataraman Subramaniam" and "Mohammed Irfan Khan" — hit
**perfect recall**. The entire PERSON recall gap comes from one category:
names that double as common English words. That's a more specific and more
useful finding than "Indian names underperform" would have been — it says
exactly what to test for in production text, instead of gesturing at an
ethnicity-shaped gap this data doesn't actually show.

Under **relaxed** matching, PERSON recall rises to 0.981 with zero false
positives — meaning most of the strict-matching gap is boundary artifacts
(a detected span that includes a trailing possessive `'s`, or drops a
common-word first name), not total misses. Exactly **one case fails under
any matching rule**:

> `PresidioNERDetector().detect("Sunny Malhotra confirmed the meeting for Tuesday.")` → `[]`

An ablation (`tests/test_sunny_ablation.py`) rules out the obvious
explanation. If "Sunny" being a common word were the cause, "Sunny Kapoor"
would fail too — it doesn't. Swapping *either* name component alone fixes
detection; sentence frame and position (subject, object, standalone, after
"Contact", after "This is") don't matter at all; prepending a title fixes
it. The actual, narrower, tested finding: this is a model-specific blind
spot for the exact bigram "Sunny Malhotra," not a generalizable "common
first names break NER" rule.

**Two concrete failure cases, reproducible in seconds:**
1. `"Sunny Malhotra confirmed the meeting for Tuesday."` → zero entities
   detected. A total miss, isolated down to the exact two-word combination
   by the ablation above — not explained by either word alone.
2. `"Ayesha Siddiqui's Aadhaar ... were verified together."` → detected
   span is `Ayesha Siddiqui's`, including the possessive. A systematic
   tokenization artifact, reproducible on every possessive construction in
   the test set (3/3), not a one-off.

### Retrieval quality

The project's framing claims naive redaction hurts retrieval; this was
previously an unmeasured assertion. `scripts/evaluate_retrieval.py` embeds
a 24-document corpus (`tests/data/retrieval_cases.py`) in three forms —
unredacted original, naive (every person → the literal string
`"[REDACTED]"`), and this pipeline (consistent `PERSON_A`/`PERSON_B`
pseudonyms) — using `all-MiniLM-L6-v2`, and ranks documents against 24
held-out queries.

| Variant | Top-1 accuracy | MRR | Mean cosine sim. to original |
|---|---|---|---|
| original | 1.000 | 1.000 | 1.000 |
| naive | 1.000 | 1.000 | 0.669 |
| pipeline | 1.000 | 1.000 | **0.687** |

**The honest read, not the flattering one:** top-1 accuracy and MRR are
tied at a perfect 1.000 across all three variants, including on the 8
documents specifically designed to stress-test entity disambiguation (two
different people, one query asking about the second person's distinct
action). That corpus design did not actually break naive redaction's
ranking — the surrounding factual content ("resolved an escalated
complaint within 48 hours" vs. "approved the loan application") was
distinctive enough on its own for the embedding model to find the right
document regardless of what happened to the names. **That is a ceiling
effect from queries being specific enough, not a win for either strategy**,
and reporting it as a win would be exactly the kind of overclaim this
project is trying not to make.

The one metric that does show a real, if modest, difference: **mean cosine
similarity to the original, unredacted embedding — 0.687 for this pipeline
vs. 0.669 for naive redaction.** Consistent pseudonymisation keeps a
document's embedding measurably closer to its unredacted original than
collapsing every person into one fixed token does. Small effect, real and
reproducible, not enough on this corpus to change which document ranks
first for these queries. A larger or harder corpus — shorter documents,
queries that lean on the entity relationship itself rather than
surrounding facts — might show the ranking-level effect this one didn't.
That's a concrete next step, not a gap papered over.

## What this project actually adds beyond calling Presidio

Presidio already detects PII. Calling `AnalyzerEngine().analyze()` is not
this project. What's actually built here, concretely:

1. **Indian-format structured detection Presidio doesn't ship.** PAN and
   Aadhaar-format numbers aren't in Presidio's default recognizer set at
   all. Aadhaar detection includes a real Verhoeff checksum implementation
   (see [`verhoeff.py`](src/pii_redaction/detectors/verhoeff.py)), not just
   a 12-digit regex.
2. **The retrieval-preservation framing and the strategy table that
   implements it** — and now a measured result on it (see above). Presidio
   redacts or anonymizes; it doesn't decide that person names should get
   *consistent* pseudonyms so a RAG system can still tell two people apart,
   or that a bare city name should be retained rather than blanked because
   it's already at the coarse end of a street→city hierarchy.
3. **Explicit overlap resolution between detector layers**, with a
   documented precedence rule. Presidio has its own internal conflict
   resolution for recognizers it manages; this project's resolution logic
   sits a layer above that, arbitrating between Presidio's NER output and
   independently-built regex/checksum detectors.
4. **A measured evaluation on an India-specific labeled test set**, not
   Presidio's own test suite — plus the retrieval-quality measurement
   above, which this project's own framing claim demanded and didn't have
   until now.
5. **An audit trail designed for compliance evidence** — offsets, entity
   type, strategy, confidence, persisted as append-only JSONL — that
   deliberately never stores the PII it's logging the redaction of.

**Why Presidio/spaCy at all, rather than building NER from scratch:**
because reimplementing a named-entity recognizer is a multi-month research
problem with worse baseline accuracy than a maintained, widely-used library
gets out of the box. The judgment call that *is* this project's own is
knowing where Presidio's defaults are wrong for this use case (its
Indian-format coverage, its blanket redaction strategy) and building
exactly those pieces — not the parts a library already does well.

## Architecture

Five stages: normalise → detect → resolve → transform → (optionally)
persist an audit trail.

### Stage 1 — Normalisation

`normalise()` applies Unicode NFKC (folds full-width digits and other
compatibility characters to canonical ASCII forms), strips zero-width
characters and the BOM, and collapses irregular whitespace. The structured
regex detectors deliberately use explicit ASCII character classes (`[2-9]`,
`[6-9]`), not `\d`, specifically so they don't accept non-ASCII digit
look-alikes — which means a full-width Aadhaar number is genuinely
invisible to the detector before this stage runs and genuinely detected
after (verified directly against the detector, not assumed from the NFKC
spec — see `tests/test_aadhaar.py`).

**This changes what offsets mean.** Every downstream offset — detected
spans, `RedactionRecord`s, anything written to an audit log — is an offset
into the *normalised* text, not the caller's original bytes. For clean
ASCII input the two are identical; they differ when the input has
full-width characters, zero-width characters, or irregular whitespace. An
auditor correlating a logged offset against a stored source document needs
to normalise that document the same way first, or the offsets won't line
up.

### Stage 2 — Detection

**Structured PII (regex + checksum):**

- Email, phone (Indian mobile formats: first digit 6-9, optional `+91`/`0`
  prefix)
- **PAN**: format `AAAA` + holder-type letter + `A` + `9999` + `A`. The 4th
  character is not a free letter — CBDT only issues 10 holder-type codes
  (`A B C F G H J L P T`). Constraining that position is a real precision
  improvement over `[A-Z]{5}\d{4}[A-Z]`, which accepts all 26 letters
  there. The 10th character is also a check character, but its generation
  algorithm is not public, so it is not validated (a documented
  limitation, not a silent gap).
- **Aadhaar**: 12 digits with a trailing Verhoeff check digit. A bare
  `\d{12}` regex fires on order numbers, tracking IDs, and other
  incidental 12-digit strings in real documents. Run `python scripts/demo.py`
  to see this concretely: on one illustrative sample document, a naive
  12-digit detector scores 0.33 precision while the checksum-validated
  detector scores 1.00. The real, dataset-wide number is in "Evaluation
  results" above.

**Unstructured PII (NER):** `PresidioNERDetector` wraps Presidio's
`AnalyzerEngine`, restricted to `PERSON` and `LOCATION` — the entity types
the regex layer structurally cannot cover. `ORGANIZATION` is intentionally
excluded: Presidio's own default config disables it ("Has many false
positives" from spaCy's noisy `ORG` label), and this project's own
transformation strategy (Stage 4) retains organisations rather than
redacting them, so detecting them isn't safety-critical here. Presidio's
spaCy recognizer also emits `NORP` and `DATE_TIME`; both are out of scope.

An earlier, small hand-written spot-check (`scripts/explore_indian_names.py`,
12 sentences, explicitly anecdotal — too small to be a recall claim) is
what first surfaced the common-word-name failure mode, before the full
134-case measurement confirmed and precisely characterized it. Kept in the
repo as the record of how the finding was actually arrived at, not
retrofitted.

### Stage 3 — Resolution

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

### Stage 4 — Transformation (the actual differentiator)

`transform.redact()` applies a different strategy per entity type — not
one blanket `[REDACTED]`:

| Entity type | Strategy | Why |
|---|---|---|
| Email, phone, PAN, Aadhaar | Fixed placeholder (e.g. `[EMAIL_REDACTED]`) | Zero retrieval value on their own, high re-identification risk |
| Person | **Consistent pseudonymisation** — every span with the same text (case-insensitive) maps to the same `PERSON_<letter>` token throughout the document | Preserves entity relationships ("PERSON_A's account" vs "PERSON_B's account") for retrieval, without revealing who either of them is |
| Location | Retained as-is | The detector only ever returns city/country-level spans (spaCy's `GPE`/`LOC`) — that's already the coarse end of a street→city coarsening strategy; there's no street-level address in scope to coarsen further, so redacting a bare city name would delete retrieval-useful context for negligible privacy gain |

Person pseudonymisation is **exact-string matching only** — there is no
coreference resolution. "Priya Sharma" and a later bare "Priya" are *not*
linked to the same token; each distinct string gets its own token the first
time it's seen (a real limitation — see Known Limitations). Pseudonym
assignment also restarts at `PERSON_A` for every call to
`redact_document()` — the same real person becomes `PERSON_A` in one
document and, say, `PERSON_C` in another. That's arguably the *correct*
privacy default (it limits cross-document linkage of a given redacted
name), but it also means cross-document retrieval can't rely on the
pseudonym token matching across documents — an unexamined consequence
worth stating rather than discovering by surprise.

Every redaction also produces a `RedactionRecord` — entity type, character
offsets, length, strategy applied, replacement, detector confidence. The
record **does not store the original PII text**, on purpose: an audit log
that keeps a plaintext copy of the exact thing it just redacted defeats the
point of redacting it.

### Stage 5 — Persisting the audit trail

`redact_document(text, audit_log_path=...)` optionally appends every
`RedactionRecord` from that call to a JSONL file — see
[`audit_log.py`](src/pii_redaction/audit_log.py). "Appends" is deliberate:
`write_audit_log()` opens in append mode by default, because a log an
application can silently overwrite isn't evidence of anything. An optional
`document_id` tags every line so records from different documents
processed into the same log file stay attributable — metadata about the
pipeline run, not PII.

Run `python scripts/demo.py` to see the full pipeline end to end, including
a persisted audit log written to `demo_audit_log.jsonl` and a concrete
instance of consistent pseudonymisation: "Priya Sharma" appears twice in
the sample text and both mentions resolve to the same `PERSON_A` token,
while "Rahul Verma" — a different person — gets the distinct `PERSON_B`.

## The labeled test set

`tests/data/cases.py` defines 134 hand-authored cases; `tests/data/build_labeled_set.py`
compiles them into [`tests/data/labeled_pii_test_set.jsonl`](tests/data/labeled_pii_test_set.jsonl).
Character offsets are **never hand-counted** — each case lists entity
substrings in reading order, and the build script locates them with
sequential string search, asserting the located text matches exactly and
that no two gold spans overlap.

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
before they'd show up as confusing evaluation results. This is explicitly
not the real evaluation (no combined-pipeline metric, no matching-rule
decision exercised here); it exists only to catch a malformed test case
before it becomes a misleading number later.

## Threats to validity

Named directly rather than left for someone else to raise:

- **This test set was authored by the same person who built the
  detectors**, before any evaluation was run against it, and before any
  detector was tuned against it. No independent labeling, no third-party
  review. Mitigated only by that ordering, and by the fact that both the
  build-time sanity check and the real evaluation surfaced real,
  unflattering failures rather than a suspiciously clean pass — a rigged
  test set would not have produced an 0.885 PERSON recall and a
  fully-missed name. What this does *not* rule out: unconscious bias in
  which sentences got written in the first place (e.g. avoiding genuinely
  hard cases without realizing it). An independent, third-party-labeled
  corpus is the real fix, and is out of scope for a solo portfolio project.
- **Sample size is small and hand-authored, not sampled from a real
  corpus.** 134 cases, ~50 PERSON mentions; the retrieval corpus is 24
  documents. The 100% regional recall numbers are consistent with no gap on
  *this data*; they are not strong evidence of no gap in general — a
  larger, corpus-sampled test set could still surface one this data is too
  small or too clean to catch.
- **LOCATION's 1.000 recall used well-known major Indian cities only**
  (Bangalore, Hyderabad, Chennai, ...). It says nothing about recall on
  smaller towns or place names that double as common words.
- **The retrieval evaluation's ranking metrics hit a ceiling** (all three
  variants tied at 1.000 top-1/MRR) because the queries were specific
  enough that non-PII content alone determined the right document. The one
  metric that moved (cosine similarity to original) is real but modest,
  and a harder corpus might reveal a larger ranking-level effect this one
  didn't surface — or might not.
- **This measures detection and retrieval-embedding similarity, not an
  end-to-end RAG answer-quality evaluation.** No generation-stage
  comparison (does the redacted-corpus RAG system produce a worse final
  answer than the unredacted one?) has been run.

## Known limitations

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
- **NER scope**: only `PERSON` and `LOCATION` are extracted (see
  Architecture, Stage 2, for why `ORGANIZATION` is excluded on purpose).
  `LOCATION` is whatever spaCy's `GPE`/`LOC` labels catch — it is not full
  postal-address parsing, so there is no street-level address to coarsen
  down to.
- **Person pseudonymisation has no coreference resolution**, and does not
  persist across separate `redact_document()` calls (see Stage 4) — both
  real, stated limitations, not hidden ones.
- **Direct identifiers only — no quasi-identifier generalisation.** This
  pipeline redacts direct identifiers (name, email, phone, PAN, Aadhaar).
  It does not address the linkage risk from combinations of *retained*
  quasi-identifiers: a retained city, plus a retained organisation, plus a
  role description can re-identify an individual even with the name
  pseudonymised. Mitigating that requires generalisation or suppression
  techniques from the k-anonymity family, operating on a whole dataset
  rather than a single document — a distinct problem class, deliberately
  out of scope here. The retained-LOCATION strategy in Stage 4 should be
  read with this in mind.
- **Audit log persistence has no rotation, encryption-at-rest, or access
  control of its own.** `write_audit_log()` appends plain JSONL to a local
  path — it's a building block for compliance evidence, not a hardened
  audit system. Those concerns belong to whatever deploys this.
- **The retrieval-quality measurement is embedding/ranking-level on a
  24-document synthetic corpus, not an end-to-end RAG evaluation** — see
  Threats to Validity for exactly what that does and doesn't show.

All test data — every Aadhaar-format number and every PAN in this repo,
including the entire labeled test set — is synthetic: generated or
hand-invented to match the real format, never a real, issued identifier.
Aadhaar numbers carry a genuinely valid Verhoeff checksum, computed
programmatically. See [`tests/fixtures.py`](tests/fixtures.py) and
[`tests/data/cases.py`](tests/data/cases.py).

## Project layout

```
src/pii_redaction/
  entity.py                  # PIIEntity — the shared span type every detector emits
  normalise.py                # Stage 1 — Unicode and whitespace normalisation
  resolution.py                # Stage 3 — resolve overlapping spans across detectors
  transform.py                  # Stage 4 — per-entity-type redaction + audit records
  pipeline.py                    # glues normalise -> detectors -> resolution -> transform (-> audit_log)
  evaluation.py                   # strict/relaxed matching, precision/recall/F1
  audit_log.py                     # Stage 5 — persisted, append-only JSONL audit trail
  detectors/
    verhoeff.py             # Verhoeff checksum (validate + generate)
    email.py
    phone.py
    pan.py
    aadhaar.py               # AadhaarDetector (checksum-validated) + AadhaarNaiveDetector (comparison only)
    ner.py                   # PresidioNERDetector — PERSON/LOCATION
tests/
  fixtures.py                # synthetic Aadhaar-number generator
  data/
    cases.py                  # raw labeled test-set case definitions (synthetic)
    build_labeled_set.py        # computes offsets, validates, writes the JSONL
    labeled_pii_test_set.jsonl   # generated — 134 cases, do not hand-edit
    retrieval_cases.py          # retrieval-quality corpus (24 docs, 24 queries, synthetic)
  test_*.py
scripts/
  demo.py                    # run the full pipeline on a sample document
  explore_indian_names.py     # anecdotal NER spot-check, not a measured eval
  evaluate.py                  # runs the detection eval, writes EVAL_RESULTS.md
  evaluate_retrieval.py          # runs the retrieval eval, writes RETRIEVAL_RESULTS.md
.github/workflows/tests.yml   # CI: pytest on every push/PR, pinned dependencies
EVAL_RESULTS.md               # generated by scripts/evaluate.py — do not hand-edit
RETRIEVAL_RESULTS.md          # generated by scripts/evaluate_retrieval.py — do not hand-edit
```

## Running

```bash
python -m venv .venv
.venv/Scripts/activate        # or source .venv/bin/activate on Linux/Mac
pip install -e . -r requirements.txt
pytest
python scripts/demo.py
python scripts/explore_indian_names.py
python tests/data/build_labeled_set.py   # regenerates labeled_pii_test_set.jsonl
python scripts/evaluate.py               # regenerates EVAL_RESULTS.md

# The retrieval evaluation needs one extra, heavier dependency not part of
# the core pipeline (sentence-transformers, which pulls in torch) - kept
# out of requirements.txt since it's only needed to run this one script:
pip install sentence-transformers
python scripts/evaluate_retrieval.py     # regenerates RETRIEVAL_RESULTS.md
```

## Scope disclaimer

This is a portfolio/reference engineering project, not a certified or
production-hardened compliance product. It is not a substitute for a formal
DPIA, legal review, or a production security assessment.
