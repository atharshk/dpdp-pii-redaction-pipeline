import pytest

from pii_redaction.pipeline import redact_document

pytestmark = pytest.mark.ner  # loads the Presidio/spaCy NER stack


def test_end_to_end_redacts_structured_and_person_entities():
    text = (
        "Priya Sharma (priya.sharma@examplebank.com, +91 98765 43210) "
        "updated her PAN to ABCPD1234E."
    )
    redacted, records = redact_document(text)

    assert "priya.sharma@examplebank.com" not in redacted
    assert "+91 98765 43210" not in redacted
    assert "ABCPD1234E" not in redacted
    assert "Priya Sharma" not in redacted
    assert "[EMAIL_REDACTED]" in redacted
    assert "[PHONE_REDACTED]" in redacted
    assert "[PAN_REDACTED]" in redacted
    assert "PERSON_A" in redacted

    strategies = {r.strategy for r in records}
    assert "placeholder_removal" in strategies
    assert "consistent_pseudonymization" in strategies


def test_same_person_referenced_twice_gets_one_consistent_token():
    text = "Rahul Verma opened the ticket. Rahul Verma closed it the same day."
    redacted, records = redact_document(text)

    person_tokens = {r.replacement for r in records if r.entity_type == "PERSON"}
    assert person_tokens == {"PERSON_A"}
    assert redacted.count("PERSON_A") == 2


def test_location_survives_redaction_for_retrieval_context():
    text = "The Bangalore office reported the issue."
    redacted, _ = redact_document(text)
    assert "Bangalore" in redacted


def test_audit_log_path_persists_records_for_this_document(tmp_path):
    from pii_redaction.audit_log import read_audit_log

    path = tmp_path / "audit.jsonl"
    text = "Contact rahul@company.co.in for details."
    _, records = redact_document(text, audit_log_path=path, document_id="doc-1")

    entries = read_audit_log(path)
    assert len(entries) == len(records) == 1
    assert entries[0]["entity_type"] == "EMAIL"
    assert entries[0]["document_id"] == "doc-1"


def test_stage1_normalisation_makes_fullwidth_aadhaar_detectable():
    # A full-width-digit Aadhaar number is invisible to the regex before
    # Stage 1 runs, because the regex uses explicit ASCII character classes
    # ([2-9], not \d) specifically so it doesn't accept non-ASCII digit
    # look-alikes. This is the concrete case Stage 1 exists for.
    fullwidth_aadhaar = "２３４５６７８９０１２４"  # NFKC -> 234567890124 (valid Verhoeff)
    text = f"Aadhaar: {fullwidth_aadhaar}"
    redacted, records = redact_document(text)
    assert "[AADHAAR_REDACTED]" in redacted
    assert any(r.entity_type == "AADHAAR" for r in records)
