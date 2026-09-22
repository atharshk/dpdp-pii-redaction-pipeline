from pii_redaction.entity import EntityType, PIIEntity

_STRUCTURED_TYPES = {EntityType.EMAIL, EntityType.PHONE, EntityType.PAN, EntityType.AADHAAR}


def _overlaps(a: PIIEntity, b: PIIEntity) -> bool:
    return a.start < b.end and b.start < a.end


def resolve(entities: list[PIIEntity]) -> list[PIIEntity]:
    """Stage 3: merge possibly-overlapping spans from multiple detectors
    into a single non-overlapping set.

    Precedence rule (documented, not the only reasonable choice):
    1. Structured, format/checksum-validated regex detectors (email, phone,
       PAN, Aadhaar) outrank the generic NER detector. Those detectors
       encode an explicit format rule NER has no equivalent for — Aadhaar's
       Verhoeff checksum, PAN's holder-type code — so a structured hit is
       trusted over an NER hit on the same characters.
    2. Within the same tier, higher confidence wins.
    3. Then longer span wins (a longer match consumed more of the
       ambiguous region, so it's less likely to be a partial/boundary
       artifact).
    4. Then earlier start offset, purely for deterministic output.

    Implementation is greedy interval scheduling: sort candidates by that
    priority and accept each one only if it doesn't overlap something
    already accepted. This is optimal for "maximize the number of accepted
    non-overlapping spans in priority order" but not for every possible
    objective (e.g. it won't backtrack to accept two shorter, lower-priority
    spans instead of one longer high-priority one that blocks both) — a
    reasonable, standard trade-off documented here rather than hidden.
    """

    def priority(e: PIIEntity) -> tuple[int, float, int, int]:
        is_structured = e.entity_type in _STRUCTURED_TYPES
        return (0 if is_structured else 1, -e.confidence, -(e.end - e.start), e.start)

    accepted: list[PIIEntity] = []
    for e in sorted(entities, key=priority):
        if not any(_overlaps(e, a) for a in accepted):
            accepted.append(e)

    return sorted(accepted, key=lambda e: e.start)
