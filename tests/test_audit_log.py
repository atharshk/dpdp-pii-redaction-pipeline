import json

from pii_redaction.audit_log import read_audit_log, write_audit_log
from pii_redaction.transform import RedactionRecord


def _record(entity_type="EMAIL", start=0, end=5):
    return RedactionRecord(
        entity_type=entity_type, start=start, end=end, original_length=end - start,
        strategy="placeholder_removal", replacement="[EMAIL_REDACTED]",
        confidence=0.95, detector="regex.email",
    )


def test_write_then_read_round_trips(tmp_path):
    path = tmp_path / "audit.jsonl"
    write_audit_log([_record()], path)
    entries = read_audit_log(path)
    assert len(entries) == 1
    assert entries[0]["entity_type"] == "EMAIL"
    assert entries[0]["start"] == 0
    assert entries[0]["end"] == 5


def test_default_mode_appends_across_calls(tmp_path):
    path = tmp_path / "audit.jsonl"
    write_audit_log([_record(start=0, end=5)], path)
    write_audit_log([_record(start=10, end=15)], path)
    entries = read_audit_log(path)
    assert len(entries) == 2
    assert [e["start"] for e in entries] == [0, 10]


def test_append_false_overwrites_previous_contents(tmp_path):
    path = tmp_path / "audit.jsonl"
    write_audit_log([_record(start=0, end=5)], path)
    write_audit_log([_record(start=99, end=104)], path, append=False)
    entries = read_audit_log(path)
    assert len(entries) == 1
    assert entries[0]["start"] == 99


def test_document_id_is_attached_when_given(tmp_path):
    path = tmp_path / "audit.jsonl"
    write_audit_log([_record()], path, document_id="ticket-42")
    entries = read_audit_log(path)
    assert entries[0]["document_id"] == "ticket-42"


def test_no_document_id_field_when_not_given(tmp_path):
    path = tmp_path / "audit.jsonl"
    write_audit_log([_record()], path)
    entries = read_audit_log(path)
    assert "document_id" not in entries[0]


def test_audit_log_never_contains_the_raw_pii_text(tmp_path):
    # RedactionRecord itself never carries the original PII text (see
    # test_transform.py), so a round-trip through the persisted log can't
    # contain it either — this is a belt-and-suspenders check on the file
    # contents themselves, not just the in-memory dataclass.
    path = tmp_path / "audit.jsonl"
    write_audit_log([_record()], path)
    raw_file_contents = path.read_text(encoding="utf-8")
    parsed = json.loads(raw_file_contents.strip())
    assert set(parsed.keys()) == {
        "entity_type", "start", "end", "original_length",
        "strategy", "replacement", "confidence", "detector",
    }


def test_read_missing_file_returns_empty_list(tmp_path):
    assert read_audit_log(tmp_path / "does_not_exist.jsonl") == []


def test_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "audit.jsonl"
    write_audit_log([_record()], path)
    assert path.exists()
