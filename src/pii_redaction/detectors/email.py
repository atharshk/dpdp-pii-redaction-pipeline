import re

from pii_redaction.entity import EntityType, PIIEntity

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}\b"
)


class EmailDetector:
    name = "regex.email"

    def detect(self, text: str) -> list[PIIEntity]:
        return [
            PIIEntity(
                entity_type=EntityType.EMAIL,
                start=m.start(),
                end=m.end(),
                text=m.group(),
                confidence=0.95,
                detector=self.name,
            )
            for m in _EMAIL_RE.finditer(text)
        ]
