from dataclasses import dataclass
from enum import Enum


class EntityType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    PAN = "PAN"
    AADHAAR = "AADHAAR"
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"


@dataclass(frozen=True)
class PIIEntity:
    """A single detected span of PII in a document."""

    entity_type: EntityType
    start: int
    end: int
    text: str
    confidence: float
    detector: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"invalid span [{self.start}, {self.end})")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence}")
