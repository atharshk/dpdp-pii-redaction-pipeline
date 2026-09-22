import re

from pii_redaction.entity import EntityType, PIIEntity

# Indian mobile numbers: 10 digits, first digit 6-9 (TRAI numbering plan),
# optional +91/0 prefix, optional space/hyphen after the 5th digit (the
# common "98765 43210" grouping). Landline numbers (STD code + local number)
# are out of scope for this detector — see README Known Limitations.
_PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")


class PhoneDetector:
    name = "regex.phone"

    def detect(self, text: str) -> list[PIIEntity]:
        return [
            PIIEntity(
                entity_type=EntityType.PHONE,
                start=m.start(),
                end=m.end(),
                text=m.group(),
                confidence=0.9,
                detector=self.name,
            )
            for m in _PHONE_RE.finditer(text)
        ]
