"""Session 5: persisting the Stage 4 audit trail.

Real audit logs are append-only — a log an application can silently
overwrite isn't evidence of anything. write_audit_log() opens in append
mode by default; each call adds new lines, it never truncates a file that
already has entries in it.

Every line is one RedactionRecord as JSON: entity type, character offsets,
length, strategy, replacement, detector confidence. As in transform.py,
this deliberately does not include a copy of the original document or the
source PII text — an audit log whose own storage becomes a second place a
data breach can leak the exact thing it was logging the redaction of would
defeat the purpose of having one.
"""

import json
from dataclasses import asdict
from pathlib import Path

from pii_redaction.transform import RedactionRecord


def write_audit_log(
    records: list[RedactionRecord], path: str | Path, *, document_id: str | None = None, append: bool = True
) -> None:
    """Append (default) or overwrite `records` as JSONL at `path`.

    `document_id` is an optional caller-supplied label (e.g. a source
    filename or ingestion job ID) written onto every line, so entries from
    different documents processed into the same log file can be told apart
    — it is metadata about the pipeline run, not PII.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8") as f:
        for record in records:
            entry = asdict(record)
            if document_id is not None:
                entry["document_id"] = document_id
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_audit_log(path: str | Path) -> list[dict]:
    """Read a JSONL audit log back as a list of plain dicts (not
    RedactionRecord instances, since a persisted entry may carry the
    optional `document_id` field RedactionRecord itself doesn't define)."""
    path = Path(path)
    if not path.exists():
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries
