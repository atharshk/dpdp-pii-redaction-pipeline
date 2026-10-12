import pytest

from pii_redaction.spans import trim_possessive


def _trimmed(text: str) -> str:
    start, end = trim_possessive(text, 0, len(text))
    return text[start:end]


@pytest.mark.parametrize(
    "span, expected",
    [
        # The three mixed-category failures in EVAL_RESULTS.md: counted as
        # FP + FN under strict matching purely because of the clitic.
        ("Ayesha Siddiqui's", "Ayesha Siddiqui"),
        ("Gurpreet Singh's", "Gurpreet Singh"),
        ("Jaspreet Bhatia's", "Jaspreet Bhatia"),
        # Typographic apostrophe: NFKC does not fold U+2019 to U+0027, so
        # this form reaches the detector intact and must be handled too.
        ("Ayesha Siddiqui’s", "Ayesha Siddiqui"),
        # Plural possessive: apostrophe with no trailing "s".
        ("the Sharmas'", "the Sharmas"),
        ("the Sharmas’", "the Sharmas"),
    ],
)
def test_trims_possessive_clitics(span, expected):
    assert _trimmed(span) == expected


@pytest.mark.parametrize(
    "span",
    [
        # Names that genuinely end in "s" must survive untouched -- this is
        # the case that rules out a naive rstrip("s").
        "Travis",
        "Paris",
        "Nikhil Das",
        # No clitic at all.
        "Ayesha Siddiqui",
        "",
    ],
)
def test_leaves_non_possessive_spans_alone(span):
    assert _trimmed(span) == span


@pytest.mark.parametrize("span", ["'s", "'", "’", "’s"])
def test_never_trims_a_span_to_nothing(span):
    # A span consisting only of a clitic is pathological, but trimming it to
    # a zero-length span would produce an entity with start == end that the
    # resolution and transformation stages are not written to handle.
    assert _trimmed(span) == span


def test_offsets_are_preserved_not_recomputed():
    # The span sits mid-string: only `end` moves, `start` must not.
    text = "Call Gurpreet Singh's office tomorrow."
    start, end = trim_possessive(text, 5, 21)
    assert text[5:21] == "Gurpreet Singh's"
    assert (start, end) == (5, 19)
    assert text[start:end] == "Gurpreet Singh"
