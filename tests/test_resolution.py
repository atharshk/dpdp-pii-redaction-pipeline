from pii_redaction.entity import EntityType, PIIEntity
from pii_redaction.resolution import resolve


def _entity(entity_type, start, end, text, confidence=0.9, detector="test"):
    return PIIEntity(
        entity_type=entity_type, start=start, end=end, text=text,
        confidence=confidence, detector=detector,
    )


def test_no_overlap_keeps_everything():
    a = _entity(EntityType.EMAIL, 0, 5, "a@b.c")
    b = _entity(EntityType.PERSON, 10, 15, "Priya")
    assert resolve([a, b]) == [a, b]


def test_structured_beats_ner_on_overlap():
    # A structured regex hit and an NER hit both claim the same characters
    # — the structured detector should win regardless of confidence.
    structured = _entity(EntityType.PHONE, 0, 10, "9876543210", confidence=0.5)
    ner = _entity(EntityType.PERSON, 0, 10, "9876543210", confidence=0.99)
    assert resolve([structured, ner]) == [structured]
    assert resolve([ner, structured]) == [structured]


def test_higher_confidence_wins_within_same_tier():
    low = _entity(EntityType.PERSON, 0, 10, "John Smith", confidence=0.6)
    high = _entity(EntityType.PERSON, 0, 10, "John Smithy", confidence=0.9)
    assert resolve([low, high]) == [high]


def test_longer_span_wins_on_confidence_tie():
    short = _entity(EntityType.PERSON, 0, 4, "John", confidence=0.85)
    long_ = _entity(EntityType.PERSON, 0, 10, "John Smith", confidence=0.85)
    assert resolve([short, long_]) == [long_]


def test_earlier_start_is_the_final_tiebreak():
    first = _entity(EntityType.PERSON, 0, 5, "Alice", confidence=0.85)
    second = _entity(EntityType.PERSON, 2, 7, "ice B", confidence=0.85)
    assert resolve([second, first]) == [first]


def test_non_overlapping_same_type_entities_both_kept():
    a = _entity(EntityType.PERSON, 0, 5, "Alice")
    b = _entity(EntityType.PERSON, 20, 25, "Priya")
    assert resolve([b, a]) == [a, b]


def test_result_is_sorted_by_start():
    a = _entity(EntityType.EMAIL, 20, 25, "a@b.c")
    b = _entity(EntityType.PHONE, 0, 10, "9876543210")
    assert [e.start for e in resolve([a, b])] == [0, 20]
