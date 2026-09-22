from pii_redaction.detectors.pan import PANDetector

detector = PANDetector()


def test_detects_valid_individual_pan():
    # 4th char 'P' = Individual (Person) — a real, valid holder-type code.
    spans = detector.detect("His PAN is ABCPD1234E for the filing.")
    assert [s.text for s in spans] == ["ABCPD1234E"]


def test_detects_valid_company_pan():
    # 4th char 'C' = Company.
    spans = detector.detect("Company PAN: AAACX5678Q registered.")
    assert [s.text for s in spans] == ["AAACX5678Q"]


def test_rejects_invalid_holder_type_code():
    # 4th char 'Z' is not one of the 10 CBDT holder-type codes — the naive
    # [A-Z]{5}\d{4}[A-Z] pattern would wrongly accept this.
    assert detector.detect("Reference code AAAZX5678Q noted.") == []


def test_does_not_match_lowercase():
    assert detector.detect("pan is abcpd1234e") == []


def test_does_not_match_wrong_digit_count():
    assert detector.detect("Code ABCPD123E is short.") == []
