import re

from pii_redaction.detectors.verhoeff import validate
from pii_redaction.entity import EntityType, PIIEntity

# Aadhaar numbers are 12 digits, first digit never 0 or 1, commonly grouped
# as 4-4-4 ("2345 6789 0123") but also appear unformatted. A bare 12-digit
# regex fires on order numbers, timestamps, and other incidental digit runs
# — see AadhaarNaiveDetector below, kept only for the precision comparison
# in README / eval. AadhaarDetector adds Verhoeff checksum validation,
# which is what actually distinguishes an Aadhaar-shaped number from noise.
_AADHAAR_RE = re.compile(r"(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")


def _digits_only(text: str) -> str:
    return re.sub(r"[\s-]", "", text)


class AadhaarNaiveDetector:
    """12-digit format match with no checksum validation. Not for production
    use — exists to demonstrate the precision cost of skipping Verhoeff."""

    name = "regex.aadhaar.naive"

    def detect(self, text: str) -> list[PIIEntity]:
        return [
            PIIEntity(
                entity_type=EntityType.AADHAAR,
                start=m.start(),
                end=m.end(),
                text=m.group(),
                confidence=0.5,
                detector=self.name,
            )
            for m in _AADHAAR_RE.finditer(text)
        ]


class AadhaarDetector:
    """Format match plus Verhoeff checksum validation."""

    name = "regex.aadhaar"

    def detect(self, text: str) -> list[PIIEntity]:
        results = []
        for m in _AADHAAR_RE.finditer(text):
            if validate(_digits_only(m.group())):
                results.append(
                    PIIEntity(
                        entity_type=EntityType.AADHAAR,
                        start=m.start(),
                        end=m.end(),
                        text=m.group(),
                        confidence=0.97,
                        detector=self.name,
                    )
                )
        return results
