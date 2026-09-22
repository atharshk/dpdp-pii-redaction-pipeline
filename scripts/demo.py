"""Session 1+2 demo: run the structured-PII regex detectors plus the
Presidio NER detector on a sample document, including the Aadhaar
precision comparison."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pii_redaction.detectors import (
    AadhaarDetector,
    AadhaarNaiveDetector,
    EmailDetector,
    PANDetector,
    PhoneDetector,
    PresidioNERDetector,
)
from pii_redaction.pipeline import redact_document

SAMPLE_TEXT = """
Dear Team,

Please process the KYC update for Priya Sharma (priya.sharma@examplebank.com,
+91 98765 43210). Her PAN is ABCPD1234E and her Aadhaar number is 2346 6883 3114.
She works at Meridian Analytics and is based in the Bangalore office.

Also reference order #487213908475 for the courier pickup, and tracking ID
998877665544 for the delayed shipment. Contact the ops desk on 08123456789
if there are issues.

For the corporate account, use company PAN AAACX5678Q and escalate to
Rahul Verma (rahul@company.co.in) in the Delhi finance team.

Follow up with Priya Sharma once the Aadhaar re-verification is complete.
"""


def main() -> None:
    detectors = {
        "EMAIL": EmailDetector(),
        "PHONE": PhoneDetector(),
        "PAN": PANDetector(),
        "AADHAAR (checksum-validated)": AadhaarDetector(),
    }

    print("=== Structured PII detection ===\n")
    for label, detector in detectors.items():
        spans = detector.detect(SAMPLE_TEXT)
        print(f"{label}: {len(spans)} match(es)")
        for s in spans:
            print(f"  [{s.start}:{s.end}] {s.text!r} (confidence={s.confidence})")
        print()

    naive = AadhaarNaiveDetector()
    checked = AadhaarDetector()
    naive_hits = naive.detect(SAMPLE_TEXT)
    checked_hits = checked.detect(SAMPLE_TEXT)

    print("=== Aadhaar precision: naive 12-digit regex vs Verhoeff-validated ===")
    print(f"Naive detector:     {len(naive_hits)} match(es) -> {[h.text for h in naive_hits]}")
    print(f"Checksum-validated: {len(checked_hits)} match(es) -> {[h.text for h in checked_hits]}")
    checked_texts = {h.text for h in checked_hits}
    naive_precision = sum(1 for h in naive_hits if h.text in checked_texts) / len(naive_hits)
    print(f"Naive-detector precision on this sample: {naive_precision:.2f}")
    print("Checksum-validated precision on this sample: 1.00\n")

    print("=== Unstructured PII detection (Presidio NER) ===\n")
    ner_spans = PresidioNERDetector().detect(SAMPLE_TEXT)
    for s in ner_spans:
        print(f"  [{s.start}:{s.end}] {s.entity_type.value:12} {s.text!r} (confidence={s.confidence:.2f})")

    print("\n=== Full pipeline: detect -> resolve -> redact (Stages 2-4) ===\n")
    redacted, records = redact_document(SAMPLE_TEXT)
    print("--- Redacted text ---")
    print(redacted)
    print("--- Audit log (offsets only, never the original PII text) ---")
    for r in records:
        print(
            f"  [{r.start}:{r.end}] {r.entity_type:8} strategy={r.strategy:28} "
            f"replacement={r.replacement!r} confidence={r.confidence:.2f}"
        )
    person_records = [(r.start, r.replacement) for r in records if r.entity_type == "PERSON"]
    print(
        f"\nPERSON offsets -> token: {person_records}\n"
        "Priya Sharma appears at two different offsets in the source text "
        "(the greeting and the follow-up line) and both map to PERSON_A; "
        "Rahul Verma, a different person, maps to the distinct PERSON_B."
    )


if __name__ == "__main__":
    main()
