"""Span-geometry helpers.

Deliberately dependency-free: span arithmetic is not NER-specific, and
keeping it out of `detectors/ner.py` means it can be unit-tested without
installing presidio-analyzer, spaCy and the ~560 MB `en_core_web_lg` model.
"""

# Possessive clitics belong to the surrounding sentence, not to the name.
# spaCy's entity spans routinely include them, so "Ayesha Siddiqui's Aadhaar
# ..." yields the span "Ayesha Siddiqui's" rather than "Ayesha Siddiqui".
# That is a tokenizer boundary artifact, not a detection failure: the name IS
# found, with the wrong end offset.
#
# Correcting it matters for a reason beyond the evaluation metric. Redacting
# the over-long span produces "PERSON_A Aadhaar ... were verified together."
# -- the possessive marker is consumed along with the name, so the sentence
# loses its grammatical relation and reads as a list rather than a statement
# about one person's Aadhaar. Trimming the clitic produces "PERSON_A's
# Aadhaar ...", which preserves it. The gain in strict precision and recall
# is a consequence of fixing the output, not the reason for the change.
#
# Deliberately narrow. The trimmed characters must begin with an apostrophe,
# so a name that genuinely ends in "s" ("Travis", "Paris") is untouched, and
# the span is never reduced to nothing. This is a rule about English
# possessive morphology, not a lookup against the test set.
#
# Both the straight apostrophe (U+0027) and the typographic one (U+2019) are
# handled: Stage 1 normalisation applies NFKC, which does NOT fold U+2019 to
# U+0027, so real documents carry both.
_POSSESSIVE_SUFFIXES = ("'s", "’s", "'", "’")


def trim_possessive(text: str, start: int, end: int) -> tuple[int, int]:
    """Return (start, end) with any trailing possessive clitic excluded.

    Offsets are into `text`. Returns the input unchanged when the span does
    not end in a possessive, or when trimming would empty it.
    """
    span = text[start:end]
    for suffix in _POSSESSIVE_SUFFIXES:
        if span.endswith(suffix) and len(span) > len(suffix):
            return start, end - len(suffix)
    return start, end
