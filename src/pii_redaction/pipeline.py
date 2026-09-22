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
    text: str, detectors: list[Detector] | None = None
) -> tuple[str, list[RedactionRecord]]:
    """Run the full Stage 2 (detection) -> Stage 3 (resolution) -> Stage 4
    (transformation) pipeline on a single document. Stage 1 (normalisation)
    and Stage 5 (persisted audit logging) are not implemented yet — see
    README Known Limitations."""
    detectors = detectors if detectors is not None else default_detectors()
    raw_entities = [entity for detector in detectors for entity in detector.detect(text)]
    resolved = resolve(raw_entities)
    return redact(text, resolved)
