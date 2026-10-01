from pii_redaction.detectors.aadhaar import AadhaarDetector, AadhaarNaiveDetector
from pii_redaction.normalise import normalise
from tests.fixtures import synthetic_aadhaar

naive = AadhaarNaiveDetector()
checked = AadhaarDetector()

# All synthetic, valid-checksum, fake Aadhaar-format numbers.
VALID_AADHAAR_1 = synthetic_aadhaar("23456789012")
VALID_AADHAAR_2 = synthetic_aadhaar("34567890123")


def test_naive_detector_matches_valid_aadhaar():
    text = f"Aadhaar number: {VALID_AADHAAR_1}"
    assert [s.text for s in naive.detect(text)] == [VALID_AADHAAR_1]


def test_checked_detector_matches_valid_aadhaar():
    text = f"Aadhaar number: {VALID_AADHAAR_1}"
    assert [s.text for s in checked.detect(text)] == [VALID_AADHAAR_1]


def test_checked_detector_handles_grouped_spacing():
    grouped = f"{VALID_AADHAAR_1[:4]} {VALID_AADHAAR_1[4:8]} {VALID_AADHAAR_1[8:]}"
    spans = checked.detect(f"UID: {grouped}")
    assert [s.text for s in spans] == [grouped]


def test_naive_detector_false_positives_on_order_number():
    # A 12-digit order number that happens to match the format but has no
    # valid Verhoeff checksum — exactly the false-positive class the naive
    # detector is vulnerable to.
    order_number = "487213908475"
    assert [s.text for s in naive.detect(f"Order #{order_number}")] == [order_number]


def test_checked_detector_rejects_order_number():
    order_number = "487213908475"
    assert checked.detect(f"Order #{order_number}") == []


def test_checked_detector_rejects_timestamp_like_number():
    # 12 digits shaped like a timestamp / sequence, invalid checksum.
    assert checked.detect("Ref: 202501151234") == []


def test_precision_delta_on_mixed_document():
    """The quotable result: on a document with one real Aadhaar-format
    number and several incidental 12-digit numbers, the naive detector's
    precision is 1/4 while the checksum-validated detector's is 1/1."""
    order_id = "487213908475"
    tracking_id = "998877665544"
    invoice_ref = "223344556677"
    text = (
        f"Aadhaar: {VALID_AADHAAR_1}. Order #{order_id}. "
        f"Tracking: {tracking_id}. Invoice ref {invoice_ref}."
    )

    naive_hits = naive.detect(text)
    checked_hits = checked.detect(text)

    assert len(naive_hits) == 4
    naive_precision = sum(1 for h in naive_hits if h.text == VALID_AADHAAR_1) / len(naive_hits)
    assert naive_precision == 0.25

    assert len(checked_hits) == 1
    assert checked_hits[0].text == VALID_AADHAAR_1


def test_fullwidth_digits_are_invisible_before_normalisation_and_detected_after():
    # The regex uses explicit ASCII [2-9], not \d, specifically so it
    # doesn't match non-ASCII digit look-alikes — which means a full-width
    # Aadhaar number needs Stage 1 normalisation to become detectable at
    # all. This is the exact mechanism Stage 1 exists for (see
    # normalise.py and pipeline.py).
    fullwidth = "".join(chr(ord(c) + 0xFEE0) if c.isdigit() else c for c in VALID_AADHAAR_1)
    text_before = f"Aadhaar: {fullwidth}"

    assert checked.detect(text_before) == []

    text_after = normalise(text_before)
    assert text_after == f"Aadhaar: {VALID_AADHAAR_1}"
    assert [s.text for s in checked.detect(text_after)] == [VALID_AADHAAR_1]
