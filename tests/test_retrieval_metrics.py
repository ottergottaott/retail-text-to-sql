import math
import pytest

from retail.retrieval_metrics import ranking_metrics, aggregate_metrics


def test_graded_ranking_uses_gain_discount_and_fixed_precision_denominator():
    # Ideal order is a(2), b(1); actual x(0), b(1), a(2).
    result = ranking_metrics(["x", "b", "a"], {"a": 2, "b": 1}, (1, 2, 5))
    assert result["1"] == {"recall": 0, "precision": 0, "rr": 0, "ndcg": 0}
    assert result["2"]["recall"] == 0.5
    assert result["2"]["precision"] == 0.5
    assert result["2"]["rr"] == 0.5
    assert result["2"]["ndcg"] == pytest.approx((1 / math.log2(3)) / (3 + 1 / math.log2(3)))
    assert result["5"]["recall"] == 1
    assert result["5"]["precision"] == 0.4
    assert result["5"]["ndcg"] == pytest.approx((1 / math.log2(3) + 3 / 2) / (3 + 1 / math.log2(3)))


def test_duplicate_results_cannot_inflate_ranking_quality():
    scores = ranking_metrics(["a", "a", "b"], {"a": 1, "b": 1}, (2,))["2"]
    assert scores["recall"] == 0.5
    assert scores["precision"] == 0.5
    assert scores["ndcg"] == pytest.approx(1 / (1 + 1 / math.log2(3)))


def test_no_relevance_has_no_positive_ranking_score():
    assert ranking_metrics(["x"], {}, (2,))["2"] == dict.fromkeys(["recall", "precision", "rr", "ndcg"])


def test_aggregation_keeps_negatives_separate_and_reports_percentiles():
    cases = [
        {"at_k": ranking_metrics(["a"], {"a": 1}, (1, 2)), "positive": True, "returned_count": 1, "latency_ms": 10},
        {"at_k": ranking_metrics([], {"a": 1}, (1, 2)), "positive": True, "returned_count": 0, "latency_ms": 20},
        {"at_k": ranking_metrics(["x"], {}, (1, 2)), "positive": False, "returned_count": 1, "latency_ms": 30},
        {"at_k": ranking_metrics([], {}, (1, 2)), "positive": False, "returned_count": 0, "latency_ms": 40},
    ]
    m = aggregate_metrics(cases, (1, 2))
    assert m["by_k"]["2"] == {"recall": 0.5, "precision": 0.25, "mrr": 0.5, "ndcg": 0.5}
    assert m["negative_false_match_rate"] == 0.5
    assert m["p50_latency_ms"] == 20
    assert m["p95_latency_ms"] == 40


@pytest.mark.parametrize("grades,cutoffs", [({"a": -1}, (2,)), ({"a": True}, (2,)), ({"a": 3}, (2,)), ({"a": 1}, (0,))])
def test_invalid_annotation_or_cutoff_is_rejected(grades, cutoffs):
    with pytest.raises(ValueError):
        ranking_metrics(["a"], grades, cutoffs)
