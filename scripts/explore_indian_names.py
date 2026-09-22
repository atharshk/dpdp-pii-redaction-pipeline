"""Session 2 exploratory check (NOT a measured evaluation): does Presidio's
default spaCy NER (en_core_web_lg, trained predominantly on Western-centric
corpora) reliably catch Indian names across regions and communities?

This is an anecdotal spot-check on a handful of hand-picked sentences, run
to form an honest expectation before Session 4 builds the real labeled test
set and measures actual recall. Do not quote these numbers as a metric —
sample size is far too small and the sentences were written, not sampled.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pii_redaction.detectors.ner import PresidioNERDetector

# (sentence, expected name substring) — spans North/South Indian, Muslim,
# Christian, and Sikh naming conventions, plus two names that are also
# common English words (a documented real failure source for NER).
CASES = [
    ("Rahul Sharma submitted the KYC form yesterday.", "Rahul Sharma"),
    ("Priya Gupta will lead the onboarding call.", "Priya Gupta"),
    ("Venkataraman Subramaniam approved the invoice.", "Venkataraman Subramaniam"),
    ("Lakshmi Narayanan is the new account owner.", "Lakshmi Narayanan"),
    ("Karthik Iyer flagged the discrepancy.", "Karthik Iyer"),
    ("Mohammed Irfan Khan signed the agreement.", "Mohammed Irfan Khan"),
    ("Ayesha Siddiqui requested a refund.", "Ayesha Siddiqui"),
    ("Maria Fernandes escalated the ticket.", "Maria Fernandes"),
    ("Gurpreet Singh confirmed the delivery address.", "Gurpreet Singh"),
    ("Harpreet Kaur updated her billing details.", "Harpreet Kaur"),
    ("Hope Fernandez called about the delayed shipment.", "Hope Fernandez"),
    ("Akash booked the appointment for Tuesday.", "Akash"),
]


def main() -> None:
    detector = PresidioNERDetector()
    hits, misses = 0, 0
    for sentence, expected in CASES:
        spans = detector.detect(sentence)
        person_texts = {s.text for s in spans if s.entity_type.value == "PERSON"}
        matched = expected in person_texts
        hits += matched
        misses += not matched
        status = "MATCH" if matched else "MISS "
        print(f"[{status}] expected={expected!r:35} got={sorted(person_texts)}")

    total = hits + misses
    print(f"\n{hits}/{total} matched exactly on this hand-picked sample.")
    print("This is NOT a recall measurement - see Session 4 for the real eval.")


if __name__ == "__main__":
    main()
