from pii_redaction.normalise import normalise


def test_nfkc_folds_fullwidth_digits_to_ascii():
    assert normalise("２３４５６７８９０１２３") == "234567890123"


def test_strips_zero_width_space_and_bom():
    assert normalise("Priya​ Sharma") == "Priya Sharma"
    assert normalise("﻿Hello") == "Hello"


def test_collapses_repeated_spaces_and_tabs():
    assert normalise("a   b\t\tc") == "a b c"


def test_collapses_three_or_more_newlines_to_two():
    assert normalise("a\n\n\n\n\nb") == "a\n\nb"


def test_preserves_a_single_blank_line():
    assert normalise("a\n\nb") == "a\n\nb"


def test_strips_leading_and_trailing_whitespace():
    assert normalise("  \n  hello world  \n  ") == "hello world"


def test_identity_on_already_clean_ascii_text():
    text = "Priya Sharma called about the invoice."
    assert normalise(text) == text


def test_does_not_touch_internal_single_newlines():
    assert normalise("line one\nline two") == "line one\nline two"
