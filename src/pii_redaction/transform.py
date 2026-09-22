from dataclasses import dataclass

from pii_redaction.entity import EntityType, PIIEntity

_PLACEHOLDER = {
    EntityType.EMAIL: "[EMAIL_REDACTED]",
    EntityType.PHONE: "[PHONE_REDACTED]",
    EntityType.PAN: "[PAN_REDACTED]",
    EntityType.AADHAAR: "[AADHAAR_REDACTED]",
}


@dataclass(frozen=True)
class RedactionRecord:
    """One audit-log entry. Deliberately does not store the original PII
    text — only its type, offsets, and length. An audit log that records
    the plaintext of the thing it just redacted would defeat the purpose;
    offsets are enough for an auditor to correlate against the original
    document under access control, without the log itself becoming a
    second copy of the PII."""

    entity_type: str
    start: int
    end: int
    original_length: int
    strategy: str
    replacement: str
    confidence: float
    detector: str


def _pseudonym_token(index: int) -> str:
    """0 -> PERSON_A, 1 -> PERSON_B, ..., 25 -> PERSON_Z, 26 -> PERSON_AA, ..."""
    letters = []
    n = index
    while True:
        n, r = divmod(n, 26)
        letters.append(chr(ord("A") + r))
        if n == 0:
            break
        n -= 1
    return "PERSON_" + "".join(reversed(letters))


def redact(text: str, entities: list[PIIEntity]) -> tuple[str, list[RedactionRecord]]:
    """Stage 4: apply the per-entity-type transformation strategy and
    return the redacted text plus an audit trail.

    `entities` must already be non-overlapping (see resolution.resolve()) —
    this function does not itself resolve conflicts.

    Strategy table:
      EMAIL / PHONE / PAN / AADHAAR -> fixed placeholder. Zero retrieval
        value on their own, high re-identification risk; no reason to
        preserve any part of them.
      PERSON -> consistent pseudonymisation: every detected span whose text
        matches (case-insensitively, exact string) maps to the same
        PERSON_<letter> token throughout this document, so a downstream RAG
        system can still tell "PERSON_A's account" from "PERSON_B's
        account" apart without ever seeing who either of them really is.
        This is exact-string matching only — there is no coreference
        resolution, so "Priya Sharma" and a later bare "Priya" are NOT
        linked to the same token (documented limitation, see README).
        Token assignment is per call, not persisted across documents.
      LOCATION -> retained as-is. The detector only ever returns city/
        country-level spans (spaCy's GPE/LOC) — that is already the coarse
        end of the "street -> city" coarsening the architecture describes;
        there is no street-level address in scope to coarsen further, so
        redacting a bare city name would just delete retrieval-useful
        context for negligible privacy gain (many people share a city).
    """
    ordered = sorted(entities, key=lambda e: e.start)
    name_to_token: dict[str, str] = {}
    records: list[RedactionRecord] = []
    pieces: list[str] = []
    cursor = 0

    for e in ordered:
        pieces.append(text[cursor : e.start])

        if e.entity_type in _PLACEHOLDER:
            replacement = _PLACEHOLDER[e.entity_type]
            strategy = "placeholder_removal"
        elif e.entity_type == EntityType.PERSON:
            key = e.text.strip().lower()
            if key not in name_to_token:
                name_to_token[key] = _pseudonym_token(len(name_to_token))
            replacement = name_to_token[key]
            strategy = "consistent_pseudonymization"
        elif e.entity_type == EntityType.LOCATION:
            replacement = e.text
            strategy = "retain"
        else:
            replacement = e.text
            strategy = "retain_unhandled_type"

        pieces.append(replacement)
        records.append(
            RedactionRecord(
                entity_type=e.entity_type.value,
                start=e.start,
                end=e.end,
                original_length=e.end - e.start,
                strategy=strategy,
                replacement=replacement,
                confidence=e.confidence,
                detector=e.detector,
            )
        )
        cursor = e.end

    pieces.append(text[cursor:])
    return "".join(pieces), records
