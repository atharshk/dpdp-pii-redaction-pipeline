"""Ablation isolating the cause of the "Sunny Malhotra" detection failure
(EVAL_RESULTS.md's sole miss under any matching rule).

The README previously described this as "'Sunny' as a common word appears
to suppress detection" — a hypothesis phrased close to a finding without
actually testing it. This file tests it. The measured result does NOT
support that hypothesis as stated:

- Swapping out "Sunny" alone (-> "Rajesh Malhotra") fixes detection.
- Swapping out "Malhotra" alone (-> "Sunny Kapoor") ALSO fixes detection.
- "Sunny" standing alone is not detected either.
- "Malhotra" standing alone IS detected.
- Sentence frame and position do not matter: the exact bigram "Sunny
  Malhotra" fails as subject, object, after a colon, and standalone.
- Prepending an honorific ("Mr Sunny Malhotra") fixes it.

So this isn't "common words suppress detection" as a general rule — if it
were, "Sunny Kapoor" would also fail, and it doesn't. The narrower, honest
finding: this specific model has a blind spot for the exact token sequence
"Sunny Malhotra" that is not explained by either token in isolation, is
insensitive to sentence frame or position, and is overridden by an
explicit honorific cue. That is a real, reproducible, but much more
specific claim than the original one-line guess.
"""

import pytest

from pii_redaction.detectors.ner import PresidioNERDetector

pytestmark = pytest.mark.ner

detector = PresidioNERDetector()


def _persons(text: str) -> list[str]:
    return [s.text for s in detector.detect(text) if s.entity_type.value == "PERSON"]


def test_baseline_fails():
    assert _persons("Sunny Malhotra confirmed the meeting for Tuesday.") == []


def test_swapping_first_name_alone_fixes_it():
    # Surname held constant, first name changed: Sunny -> Rajesh.
    assert _persons("Rajesh Malhotra confirmed the meeting for Tuesday.") == ["Rajesh Malhotra"]


def test_swapping_surname_alone_also_fixes_it():
    # First name held constant, surname changed: Malhotra -> Kapoor.
    # This is the result that rules out "Sunny is just a bad first name
    # for this model" as the explanation — if it were, this would still fail.
    assert _persons("Sunny Kapoor confirmed the meeting for Tuesday.") == ["Sunny Kapoor"]


def test_surname_alone_is_detected():
    assert _persons("Malhotra confirmed the meeting for Tuesday.") == ["Malhotra"]


def test_first_name_alone_is_not_detected():
    # "Sunny" in isolation, as a sentence subject, is also missed — it is
    # not simply that "Malhotra" needs a different companion; "Sunny" alone
    # doesn't read as PERSON either.
    assert _persons("Sunny confirmed the meeting for Tuesday.") == []


def test_prepending_an_honorific_title_fixes_it():
    assert _persons("Mr Sunny Malhotra confirmed the meeting for Tuesday.") == ["Sunny Malhotra"]


@pytest.mark.parametrize(
    "text",
    [
        "Sunny Malhotra is a software engineer.",
        "Sunny Malhotra called.",
        "Sunny Malhotra, our new hire, confirmed the meeting for Tuesday.",
        "I spoke with Sunny Malhotra about the meeting.",
        "The invoice was approved by Sunny Malhotra yesterday.",
        "Sunny Malhotra",
        "This is Sunny Malhotra.",
        "Contact Sunny Malhotra for details.",
    ],
)
def test_failure_is_insensitive_to_sentence_frame_and_position(text):
    # Different predicates, different sentence lengths, subject position,
    # object position, standalone, after a colon-like "This is" / "Contact"
    # construction — the bigram fails in all of them. This rules out
    # "sentence context/frame" as the explanation.
    assert _persons(text) == []
