import re

from pii_redaction.entity import EntityType, PIIEntity

# PAN structure: AAAA A 9999 A
#   chars 1-3: alphabetic series (no constraint)
#   char 4:    holder-type code — one of the 10 values CBDT actually issues
#   char 5:    first letter of surname/entity name (no constraint we can check)
#   chars 6-9: sequence number
#   char 10:   alphabetic check character (not a public checksum algorithm;
#              we do not validate it, see README Known Limitations)
#
# Constraining char 4 to valid holder-type codes is a real precision gain
# over a naive [A-Z]{5}\d{4}[A-Z] pattern, which accepts 26 possibilities
# for that position instead of 10.
_HOLDER_TYPE_CODES = "ABCFGHJLPT"

_PAN_RE = re.compile(
    rf"\b[A-Z]{{3}}[{_HOLDER_TYPE_CODES}][A-Z]\d{{4}}[A-Z]\b"
)


class PANDetector:
    name = "regex.pan"

    def detect(self, text: str) -> list[PIIEntity]:
        return [
            PIIEntity(
                entity_type=EntityType.PAN,
                start=m.start(),
                end=m.end(),
                text=m.group(),
                confidence=0.9,
                detector=self.name,
            )
            for m in _PAN_RE.finditer(text)
        ]
