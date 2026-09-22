"""Verhoeff checksum algorithm.

Aadhaar numbers are 12-digit identifiers where the final digit is a Verhoeff
check digit over the preceding 11. A naive `\\d{12}` regex fires on any
12-digit string (order numbers, timestamps, phone concatenations); checksum
validation is what turns that into a precise Aadhaar-format detector.

Reference: Jacobus Verhoeff, "Error Detecting Decimal Codes" (1969).
"""

_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)

_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)

_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def validate(number: str) -> bool:
    """Return True if `number` (all digits, check digit included) passes Verhoeff."""
    if not number.isdigit():
        return False
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(digit)]]
    return c == 0


def generate_check_digit(number_without_check_digit: str) -> str:
    """Compute the Verhoeff check digit for a digit string (used to synthesize
    valid-checksum test fixtures — never for real identifiers)."""
    if not number_without_check_digit.isdigit():
        raise ValueError("input must be all digits")
    c = 0
    for i, digit in enumerate(reversed(number_without_check_digit)):
        c = _D[c][_P[(i + 1) % 8][int(digit)]]
    return str(_INV[c])
