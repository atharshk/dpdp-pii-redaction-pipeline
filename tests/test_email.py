from pii_redaction.detectors.email import EmailDetector

detector = EmailDetector()


def test_detects_simple_email():
    text = "Contact priya.sharma@example.com for details."
    spans = detector.detect(text)
    assert len(spans) == 1
    assert spans[0].text == "priya.sharma@example.com"


def test_detects_multiple_emails():
    text = "cc rahul@company.co.in and admin@sub.domain.org"
    spans = detector.detect(text)
    assert {s.text for s in spans} == {"rahul@company.co.in", "admin@sub.domain.org"}


def test_no_match_in_plain_text():
    text = "The meeting is scheduled for 3pm tomorrow."
    assert detector.detect(text) == []


def test_does_not_match_bare_at_symbol():
    text = "He said @ the meeting that things went well."
    assert detector.detect(text) == []
