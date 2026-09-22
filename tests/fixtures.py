"""Synthetic test-data generators. Never use real identifiers in this repo."""

from pii_redaction.detectors.verhoeff import generate_check_digit


def synthetic_aadhaar(base11: str) -> str:
    """Build a valid-checksum, fake Aadhaar-format number from an 11-digit
    base (first digit must be 2-9 per UIDAI spec). Synthetic only."""
    if len(base11) != 11 or not base11.isdigit() or base11[0] in "01":
        raise ValueError("base11 must be 11 digits, first digit 2-9")
    return base11 + generate_check_digit(base11)
