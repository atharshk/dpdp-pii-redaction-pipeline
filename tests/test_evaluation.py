import pytest

from pii_redaction.entity import EntityType, PIIEntity
from pii_redaction.evaluation import Confusion, evaluate_dataset, f1, precision, recall


def _pred(entity_type, start, end, text, confidence=0.9):
    return PIIEntity(entity_type, start, end, text, confidence, "test")


def _gold(entity_type, start, end, text):
    return {"type": entity_type, "start": start, "end": end, "text": text}


def test_precision_recall_f1_basic():
    c = Confusion(tp=8, fp=2, fn=2)
    assert precision(c) == 0.8
    assert recall(c) == 0.8
    assert f1(c) == pytest.approx(0.8)


def test_precision_recall_undefined_when_denominator_zero():
    assert precision(Confusion(tp=0, fp=0, fn=5)) is None
    assert recall(Confusion(tp=0, fp=5, fn=0)) is None
    assert f1(Confusion(tp=0, fp=0, fn=0)) is None


def test_exact_match_is_a_true_positive_under_strict_and_relaxed():
    records = [{
        "id": "0", "category": "email", "text": "a@b.com",
        "entities": [_gold("EMAIL", 0, 7, "a@b.com")],
    }]
    predict = lambda text: [_pred(EntityType.EMAIL, 0, 7, "a@b.com")]

    for rule in ("strict", "relaxed"):
        result = evaluate_dataset(records, predict, rule)
        assert result.per_type["EMAIL"] == Confusion(tp=1, fp=0, fn=0)


def test_boundary_mismatch_is_fn_plus_fp_under_strict_but_tp_under_relaxed():
    # Predicted span includes a trailing character gold doesn't — exactly
    # the possessive-'s pattern found in Session 3.
    records = [{
        "id": "0", "category": "person_test", "text": "Ayesha Siddiqui's",
        "entities": [_gold("PERSON", 0, 15, "Ayesha Siddiqui")],
    }]
    predict = lambda text: [_pred(EntityType.PERSON, 0, 17, "Ayesha Siddiqui's")]

    strict = evaluate_dataset(records, predict, "strict")
    assert strict.per_type["PERSON"] == Confusion(tp=0, fp=1, fn=1)

    relaxed = evaluate_dataset(records, predict, "relaxed")
    assert relaxed.per_type["PERSON"] == Confusion(tp=1, fp=0, fn=0)


def test_missed_gold_entity_is_a_false_negative():
    records = [{
        "id": "0", "category": "email", "text": "no match here",
        "entities": [_gold("EMAIL", 0, 5, "a@b.com")],
    }]
    predict = lambda text: []
    result = evaluate_dataset(records, predict, "strict")
    assert result.per_type["EMAIL"] == Confusion(tp=0, fp=0, fn=1)
    assert len(result.failures) == 1
    assert result.failures[0].kind == "FN"


def test_spurious_prediction_on_negative_case_is_a_false_positive():
    records = [{
        "id": "0", "category": "negative_no_pii", "text": "nothing sensitive",
        "entities": [],
    }]
    predict = lambda text: [_pred(EntityType.PERSON, 0, 7, "nothing")]
    result = evaluate_dataset(records, predict, "strict")
    assert result.per_type["PERSON"] == Confusion(tp=0, fp=1, fn=0)
    assert result.failures[0].kind == "FP"


def test_wrong_type_at_same_offsets_does_not_match():
    records = [{
        "id": "0", "category": "mixed", "text": "9876543210",
        "entities": [_gold("PHONE", 0, 10, "9876543210")],
    }]
    predict = lambda text: [_pred(EntityType.PERSON, 0, 10, "9876543210")]
    result = evaluate_dataset(records, predict, "relaxed")
    assert result.per_type["PHONE"] == Confusion(tp=0, fp=0, fn=1)
    assert result.per_type["PERSON"] == Confusion(tp=0, fp=1, fn=0)


def test_duplicate_gold_entities_match_one_to_one_not_many_to_one():
    # Two identical gold PERSON spans (two different people, same name text,
    # different offsets) must each require their own matching prediction —
    # one prediction should not satisfy both.
    records = [{
        "id": "0", "category": "person_test", "text": "Raj met Raj again",
        "entities": [_gold("PERSON", 0, 3, "Raj"), _gold("PERSON", 8, 11, "Raj")],
    }]
    predict = lambda text: [_pred(EntityType.PERSON, 0, 3, "Raj")]
    result = evaluate_dataset(records, predict, "strict")
    assert result.per_type["PERSON"] == Confusion(tp=1, fp=0, fn=1)


def test_person_by_category_only_tracks_person_prefixed_categories():
    records = [
        {
            "id": "0", "category": "person_sikh", "text": "Gurpreet Singh called.",
            "entities": [_gold("PERSON", 0, 14, "Gurpreet Singh")],
        },
        {
            "id": "1", "category": "mixed", "text": "Rahul Verma called.",
            "entities": [_gold("PERSON", 0, 11, "Rahul Verma")],
        },
    ]
    predict = lambda text: []  # miss everything
    result = evaluate_dataset(records, predict, "strict")
    assert "person_sikh" in result.person_by_category
    assert "mixed" not in result.person_by_category
    # but the overall PERSON count still includes the mixed-category miss
    assert result.per_type["PERSON"].fn == 2
