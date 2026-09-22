"""Session 4: evaluation of detection+resolution (Stage 2+3) against a
labeled test set.

Matching rule — decided and documented here, before any number is computed,
per the project's own ground rule that an undefined matching rule is how
meaningless precision/recall scores get produced:

  STRICT  (primary, reported number): a predicted span counts as correct
    only if its entity type AND exact character offsets match a gold span.
    This is the standard exact-match convention in NER evaluation (e.g.
    CoNLL-style scoring) and is the more conservative choice — it does not
    give credit for a span that overlaps the right answer but got the
    boundary wrong.

  RELAXED (diagnostic companion, not the headline number): a predicted span
    counts as correct if its entity type matches and it overlaps the gold
    span at all. Reported alongside strict specifically to characterize
    *why* strict recall is lower than it might look — e.g. Session 3's
    build-time sanity check already found predicted spans that include a
    trailing possessive "'s" the gold span excludes. Relaxed is not used as
    the reported number because it would silently give full credit for
    exactly that kind of boundary slop.

Both numbers are computed and reported side by side — never only whichever
one looks better.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Literal

from pii_redaction.entity import PIIEntity

MatchingRule = Literal["strict", "relaxed"]


@dataclass
class Confusion:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __add__(self, other: "Confusion") -> "Confusion":
        return Confusion(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)


def precision(c: Confusion) -> float | None:
    denom = c.tp + c.fp
    return c.tp / denom if denom else None


def recall(c: Confusion) -> float | None:
    denom = c.tp + c.fn
    return c.tp / denom if denom else None


def f1(c: Confusion) -> float | None:
    p, r = precision(c), recall(c)
    if p is None or r is None or (p + r) == 0:
        return None
    return 2 * p * r / (p + r)


@dataclass
class Failure:
    kind: Literal["FN", "FP"]
    case_id: str
    category: str
    entity_type: str
    span_text: str
    text: str


@dataclass
class EvalResult:
    rule: MatchingRule
    per_type: dict[str, Confusion] = field(default_factory=lambda: defaultdict(Confusion))
    person_by_category: dict[str, Confusion] = field(default_factory=lambda: defaultdict(Confusion))
    failures: list[Failure] = field(default_factory=list)

    def overall(self) -> Confusion:
        total = Confusion()
        for c in self.per_type.values():
            total = total + c
        return total


def _spans_match(pred: PIIEntity, gold: dict, rule: MatchingRule) -> bool:
    if pred.entity_type.value != gold["type"]:
        return False
    if rule == "strict":
        return pred.start == gold["start"] and pred.end == gold["end"]
    return pred.start < gold["end"] and gold["start"] < pred.end  # relaxed: any overlap


def _match_case(
    predicted: list[PIIEntity], gold_entities: list[dict], rule: MatchingRule
) -> tuple[list[tuple[PIIEntity, dict]], list[dict], list[PIIEntity]]:
    """Greedy one-to-one matching per case. Returns (matched pairs, unmatched
    gold entities, unmatched predictions)."""
    unmatched_gold = list(gold_entities)
    unmatched_pred = list(predicted)
    matched_pairs = []
    for gold in list(unmatched_gold):
        candidate = next((p for p in unmatched_pred if _spans_match(p, gold, rule)), None)
        if candidate is not None:
            matched_pairs.append((candidate, gold))
            unmatched_pred.remove(candidate)
            unmatched_gold.remove(gold)
    return matched_pairs, unmatched_gold, unmatched_pred


def evaluate_dataset(
    records: list[dict],
    predict_fn: Callable[[str], list[PIIEntity]],
    rule: MatchingRule,
) -> EvalResult:
    result = EvalResult(rule=rule)

    for r in records:
        predicted = predict_fn(r["text"])
        matched_pairs, unmatched_gold, unmatched_pred = _match_case(predicted, r["entities"], rule)

        for _pred, gold in matched_pairs:
            result.per_type[gold["type"]].tp += 1
            if r["category"].startswith("person_"):
                result.person_by_category[r["category"]].tp += 1

        for gold in unmatched_gold:
            result.per_type[gold["type"]].fn += 1
            if r["category"].startswith("person_"):
                result.person_by_category[r["category"]].fn += 1
            result.failures.append(
                Failure("FN", r["id"], r["category"], gold["type"], gold["text"], r["text"])
            )

        for pred in unmatched_pred:
            result.per_type[pred.entity_type.value].fp += 1
            if r["category"].startswith("person_"):
                result.person_by_category[r["category"]].fp += 1
            result.failures.append(
                Failure("FP", r["id"], r["category"], pred.entity_type.value, pred.text, r["text"])
            )

    return result
