import dataclasses

from pii_redaction.entity import EntityType, PIIEntity
from pii_redaction.transform import RedactionRecord, redact


def _entity(entity_type, start, end, text, confidence=0.9, detector="test"):
    return PIIEntity(
        entity_type=entity_type, start=start, end=end, text=text,
        confidence=confidence, detector=detector,
    )


def test_structured_types_become_fixed_placeholders():
    text = "Email a@b.com or call 9876543210."
    email_start = text.index("a@b.com")
    phone_start = text.index("9876543210")
    entities = [
        _entity(EntityType.EMAIL, email_start, email_start + len("a@b.com"), "a@b.com"),
        _entity(EntityType.PHONE, phone_start, phone_start + len("9876543210"), "9876543210"),
    ]
    redacted, records = redact(text, entities)
    assert redacted == "Email [EMAIL_REDACTED] or call [PHONE_REDACTED]."
    assert {r.strategy for r in records} == {"placeholder_removal"}


def test_same_person_name_gets_same_token_every_time():
    text = "Priya Sharma called. Later, Priya Sharma called again."
    first = text.index("Priya Sharma")
    second = text.index("Priya Sharma", first + 1)
    entities = [
        _entity(EntityType.PERSON, first, first + 12, "Priya Sharma"),
        _entity(EntityType.PERSON, second, second + 12, "Priya Sharma"),
    ]
    redacted, records = redact(text, entities)
    tokens = [r.replacement for r in records]
    assert tokens[0] == tokens[1]
    assert redacted.count(tokens[0]) == 2


def test_case_insensitive_name_matching_maps_to_same_token():
    text = "PRIYA SHARMA and priya sharma are the same person in this test."
    first = text.index("PRIYA SHARMA")
    second = text.index("priya sharma")
    entities = [
        _entity(EntityType.PERSON, first, first + 12, "PRIYA SHARMA"),
        _entity(EntityType.PERSON, second, second + 12, "priya sharma"),
    ]
    _, records = redact(text, entities)
    assert records[0].replacement == records[1].replacement


def test_different_names_get_different_tokens_in_order_of_first_appearance():
    text = "Rahul met Priya, then Rahul met Karthik."
    positions = []
    for name in ["Rahul", "Priya", "Rahul", "Karthik"]:
        start = text.index(name, positions[-1][1] if positions else 0)
        positions.append((start, start + len(name)))
    entities = [_entity(EntityType.PERSON, s, e, text[s:e]) for s, e in positions]
    _, records = redact(text, entities)
    tokens = [r.replacement for r in records]
    assert tokens == ["PERSON_A", "PERSON_B", "PERSON_A", "PERSON_C"]


def test_location_is_retained_not_redacted():
    text = "Based in Bangalore."
    entities = [_entity(EntityType.LOCATION, 9, 18, "Bangalore")]
    redacted, records = redact(text, entities)
    assert redacted == text
    assert records[0].strategy == "retain"


def test_audit_record_never_stores_the_original_pii_text():
    # The record's own fields must not include a field holding the raw
    # detected PII string — offsets + type are enough for an auditor,
    # and storing the plaintext would defeat the point of an audit log.
    field_names = {f.name for f in dataclasses.fields(RedactionRecord)}
    assert "text" not in field_names
    assert "original_text" not in field_names
    assert "value" not in field_names


def test_audit_record_offsets_match_source_span():
    text = "PAN ABCPD1234E on file."
    entities = [_entity(EntityType.PAN, 4, 14, "ABCPD1234E")]
    _, records = redact(text, entities)
    assert records[0].start == 4
    assert records[0].end == 14
    assert records[0].original_length == 10
    assert records[0].entity_type == "PAN"


def test_text_outside_entities_is_preserved_verbatim():
    text = "Before Priya Sharma after."
    start = text.index("Priya Sharma")
    entities = [_entity(EntityType.PERSON, start, start + 12, "Priya Sharma")]
    redacted, _ = redact(text, entities)
    assert redacted.startswith("Before ")
    assert redacted.endswith(" after.")


def test_no_entities_returns_text_unchanged():
    text = "Nothing sensitive here."
    redacted, records = redact(text, [])
    assert redacted == text
    assert records == []
