from functools import lru_cache

from presidio_analyzer import AnalyzerEngine

from pii_redaction.entity import EntityType, PIIEntity

# Structured PII (email, phone, PAN, Aadhaar) is already covered by the
# regex detectors with format/checksum precision Presidio's generic
# recognizers can't match for Indian formats. This detector is restricted
# to the unstructured entity types the regex layer can't cover at all.
#
# ORGANIZATION is deliberately excluded: Presidio's own default config
# (conf/default.yaml) disables it, with the comment "Has many false
# positives" — spaCy's ORG label is noisy. This is a defensible default to
# keep rather than override, since the project's own transformation
# strategy (README Stage 4) retains organisations rather than redacting
# them; detecting them isn't safety-critical the way PERSON detection is.
# Presidio's spaCy-backed recognizer also emits NRP and DATE_TIME; those
# are out of scope for this session too (see README Known Limitations).
_SUPPORTED_ENTITIES = ("PERSON", "LOCATION")


@lru_cache(maxsize=1)
def _get_analyzer() -> AnalyzerEngine:
    # Presidio's default NLP config uses en_core_web_lg for English — loading
    # the model is expensive, so the engine is built once per process and
    # shared across detector instances.
    return AnalyzerEngine()


class PresidioNERDetector:
    """Wraps Presidio's AnalyzerEngine (spaCy en_core_web_lg) for person
    names, organisations, and locations."""

    name = "ner.presidio"

    def __init__(self) -> None:
        self._engine = _get_analyzer()

    def detect(self, text: str) -> list[PIIEntity]:
        results = self._engine.analyze(
            text=text, language="en", entities=list(_SUPPORTED_ENTITIES)
        )
        return [
            PIIEntity(
                entity_type=EntityType(r.entity_type),
                start=r.start,
                end=r.end,
                text=text[r.start : r.end],
                confidence=r.score,
                detector=self.name,
            )
            for r in results
        ]
