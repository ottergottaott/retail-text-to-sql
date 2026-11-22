import math
import pytest

from retail.bm25 import BM25


def test_bm25_scores_match_independently_calculated_term_frequency_and_length():
    index = BM25({"a": "sales sales", "b": "returns", "c": "sales returns"})
    results = index.search("sales", k=2)
    # N=3, df=2, average length=5/3; k1=1.2, b=.75.
    idf = math.log(1 + 1.5 / 2.5)
    expected_a = idf * 2 * 2.2 / (2 + 1.2 * (0.25 + 0.75 * 2 / (5 / 3)))
    assert results[0]["id"] == "a"
    assert results[0]["score"] == pytest.approx(expected_a)
    assert [x["id"] for x in results] == ["a", "c"]


def test_bm25_preserves_no_match_and_unicode_tokens():
    index = BM25({"en": "monthly revenue", "ru": "месячная выручка"})
    assert index.search("weather") == []
    assert index.search("выручка")[0]["id"] == "ru"


def test_bm25_ties_are_deterministic():
    assert [r["id"] for r in BM25({"b": "sales", "a": "sales"}).search("sales")] == ["a", "b"]
