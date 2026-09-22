from pii_redaction.detectors.phone import PhoneDetector

detector = PhoneDetector()


def test_detects_plain_10_digit():
    spans = detector.detect("Call me at 9876543210 today.")
    assert [s.text for s in spans] == ["9876543210"]


def test_detects_with_country_code_plus():
    spans = detector.detect("Reach him on +91 9876543210.")
    assert [s.text for s in spans] == ["+91 9876543210"]


def test_detects_with_hyphen_country_code():
    spans = detector.detect("+91-9876543210 is the number.")
    assert [s.text for s in spans] == ["+91-9876543210"]


def test_detects_grouped_with_space():
    spans = detector.detect("My number is 98765 43210.")
    assert [s.text for s in spans] == ["98765 43210"]


def test_detects_with_leading_zero():
    spans = detector.detect("Landline forwarding: 09876543210")
    assert [s.text for s in spans] == ["09876543210"]


def test_does_not_match_number_starting_with_5():
    # Indian mobile numbers start with 6-9, not 5.
    assert detector.detect("Order quantity: 5876543210 units") == []


def test_does_not_match_part_of_longer_digit_run():
    assert detector.detect("Tracking ID: 987654321099887766") == []
