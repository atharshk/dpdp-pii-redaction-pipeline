from pathlib import Path

from pii_redaction.audit_log import write_audit_log
from pii_redaction.detectors import (
    AadhaarDetector,
    EmailDetector,
    PANDetector,
    PhoneDetector,
    PresidioNERDetector,
)
from pii_redaction.detectors.base import Detector
from pii_redaction.resolution import resolve
from pii_redaction.transform import RedactionRecord, redact


def default_detectors() -> list[Detector]:
    # PresidioNERDetector loads a spaCy model on first use (via its shared,
    # cached AnalyzerEngine) — built lazily here rather than at import time.
    return [EmailDetector(), PhoneDetector(), PANDetector(), AadhaarDetector(), PresidioNERDetector()]


def redact_document(
    text: str,
    detectors: list[Detector] | None = None,
    *,
    audit_log_path: str | Path | None = None,
    document_id: str | None = None,
) -> tuple[str, list[RedactionRecord]]:
    """Run the full Stage 2 (detection) -> Stage 3 (resolution) -> Stage 4
    (transformation) pipeline on a single document.

    If `audit_log_path` is given, the resulting RedactionRecords are also
    appended to that path as JSONL (see audit_log.write_audit_log) —
    Stage 5's persisted audit trail. Without it, records are only returned
    in-memory, as before. Stage 1 (normalisation) is not implemented yet —
    see README Known Limitations.
    """
    detectors = detectors if detectors is not None else default_detectors()
    raw_entities = [entity for detector in detectors for entity in detector.detect(text)]
    resolved = resolve(raw_entities)
    redacted_text, records = redact(text, resolved)
    if audit_log_path is not None:
        write_audit_log(records, audit_log_path, document_id=document_id)
    return redacted_text, records
