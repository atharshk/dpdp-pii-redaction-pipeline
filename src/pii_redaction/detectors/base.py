from typing import Protocol

from pii_redaction.entity import PIIEntity


class Detector(Protocol):
    """A detector scans normalised text and returns the PII spans it finds."""

    def detect(self, text: str) -> list[PIIEntity]: ...
