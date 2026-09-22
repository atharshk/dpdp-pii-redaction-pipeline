from pii_redaction.detectors.verhoeff import generate_check_digit, validate


def test_known_verhoeff_vector():
    # 236 -> check digit 3 is a standard published test vector for this algorithm.
    assert generate_check_digit("236") == "3"
    assert validate("2363")


def test_generated_check_digit_round_trips():
    base = "23456789012"
    check_digit = generate_check_digit(base)
    assert validate(base + check_digit)


def test_single_digit_transcription_error_detected():
    base = "23456789012"
    number = base + generate_check_digit(base)
    tampered = "3" + number[1:]  # flip the first digit
    assert not validate(tampered)


def test_non_digit_input_is_invalid():
    assert not validate("12345abcde12")
