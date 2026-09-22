import pytest

from pii_redaction.detectors.ner import PresidioNERDetector

pytestmark = pytest.mark.ner

detector = PresidioNERDetector()


def _texts_by_type(spans, entity_type):
    return {s.text for s in spans if s.entity_type.value == entity_type}


def test_detects_a_clear_western_person_name():
    spans = detector.detect("John Smith joined the meeting at 3pm.")
    assert "John Smith" in _texts_by_type(spans, "PERSON")


def test_organization_is_deliberately_not_detected():
    # Presidio's own default config disables the ORGANIZATION recognizer
    # ("Has many false positives" — see ner.py). This test documents that
    # exclusion as intended behavior, not a gap to silently fix.
    spans = detector.detect("She works at Microsoft in the Azure team.")
    assert _texts_by_type(spans, "ORGANIZATION") == set()


def test_detects_a_clear_location():
    spans = detector.detect("The office relocated to Mumbai last year.")
    assert "Mumbai" in _texts_by_type(spans, "LOCATION")


def test_no_match_on_pii_free_text():
    spans = detector.detect("The quarterly report is due next Friday.")
    assert spans == []


def test_returned_spans_index_correctly_into_source_text():
    text = "Contact John Smith about the invoice."
    spans = detector.detect(text)
    for s in spans:
        assert text[s.start : s.end] == s.text
