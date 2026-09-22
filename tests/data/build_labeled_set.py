"""Builds tests/data/labeled_pii_test_set.jsonl from tests/data/cases.py.

Character offsets are computed here, never hand-typed in cases.py: each
entity's exact substring is located by sequential search over the sentence.
This is deliberate — a hand-counted offset is exactly the kind of unchecked
claim this project's own ground rule forbids. If a substring can't be
found, or two entities claim overlapping spans, the build fails loudly
instead of silently writing a bad label.

Also runs a build-time sanity check: each gold entity is checked against
its own single-purpose detector (regex detector for structured types, the
NER detector for PERSON/LOCATION). This is NOT the Session 4 evaluation —
no combined-pipeline precision/recall/F1 is computed here, no matching-rule
decision is exercised — it exists only to catch authoring mistakes in this
test set (a malformed PAN, a phone format the regex doesn't cover) before
they become confusing results in Session 4.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.data.cases import CASES  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent / "labeled_pii_test_set.jsonl"


def compute_offsets(case_id: str, text: str, entities: list[tuple[str, str]]) -> list[dict]:
    resolved = []
    cursor = 0
    for entity_type, entity_text in entities:
        start = text.find(entity_text, cursor)
        if start == -1:
            raise ValueError(
                f"[{case_id}] could not locate {entity_text!r} ({entity_type}) "
                f"in text after position {cursor}: {text!r}"
            )
        end = start + len(entity_text)
        if text[start:end] != entity_text:
            raise AssertionError(f"[{case_id}] offset mismatch for {entity_text!r}")
        resolved.append({"type": entity_type, "start": start, "end": end, "text": entity_text})
        cursor = end
    return resolved


def check_no_overlaps(case_id: str, entities: list[dict]) -> None:
    ordered = sorted(entities, key=lambda e: e["start"])
    for prev, curr in zip(ordered, ordered[1:]):
        if curr["start"] < prev["end"]:
            raise AssertionError(f"[{case_id}] overlapping gold spans: {prev} vs {curr}")


def build() -> list[dict]:
    records = []
    seen_ids = set()
    for i, (category, text, entities) in enumerate(CASES):
        case_id = f"{i:04d}"
        assert case_id not in seen_ids
        seen_ids.add(case_id)
        resolved = compute_offsets(case_id, text, entities)
        check_no_overlaps(case_id, resolved)
        records.append({"id": case_id, "category": category, "text": text, "entities": resolved})
    return records


def write_jsonl(records: list[dict]) -> None:
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def print_summary(records: list[dict]) -> None:
    by_category: dict[str, int] = {}
    by_entity_type: dict[str, int] = {}
    for r in records:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1
        for e in r["entities"]:
            by_entity_type[e["type"]] = by_entity_type.get(e["type"], 0) + 1

    print(f"Total cases: {len(records)}")
    print(f"Total gold entities: {sum(by_entity_type.values())}\n")
    print("By category:")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat:28} {count}")
    print("\nBy entity type:")
    for et, count in sorted(by_entity_type.items()):
        print(f"  {et:12} {count}")


def sanity_check_against_detectors(records: list[dict]) -> None:
    """Run each gold entity against its own single-purpose detector and flag
    anything the detector fails to reproduce. Diagnostic only — see module
    docstring."""
    from pii_redaction.detectors.aadhaar import AadhaarDetector
    from pii_redaction.detectors.email import EmailDetector
    from pii_redaction.detectors.ner import PresidioNERDetector
    from pii_redaction.detectors.pan import PANDetector
    from pii_redaction.detectors.phone import PhoneDetector

    regex_detectors = {
        "EMAIL": EmailDetector(),
        "PHONE": PhoneDetector(),
        "PAN": PANDetector(),
        "AADHAAR": AadhaarDetector(),
    }
    ner = PresidioNERDetector()

    misses = []
    for r in records:
        text = r["text"]
        regex_hits = {
            t: {s.text for s in d.detect(text)} for t, d in regex_detectors.items()
        }
        ner_hits = {s.text for s in ner.detect(text)}

        for e in r["entities"]:
            if e["type"] in regex_detectors:
                if e["text"] not in regex_hits[e["type"]]:
                    misses.append((r["id"], e["type"], e["text"], text))
            elif e["type"] in ("PERSON", "LOCATION"):
                if e["text"] not in ner_hits:
                    misses.append((r["id"], e["type"], e["text"], text))

    print(f"\nBuild-time sanity check: {len(misses)} gold entity(ies) not reproduced by their own detector.")
    for case_id, etype, etext, text in misses:
        print(f"  [{case_id}] {etype:8} {etext!r} not found in: {text!r}")
    if not misses:
        print("  None — every gold entity is independently detectable.")


def main() -> None:
    records = build()
    write_jsonl(records)
    print(f"Wrote {len(records)} cases to {OUTPUT_PATH}\n")
    print_summary(records)
    sanity_check_against_detectors(records)


if __name__ == "__main__":
    main()
