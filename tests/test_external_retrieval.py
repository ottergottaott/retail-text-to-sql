import pytest

from retail.external_retrieval import evaluate_external
from retail.embeddings import EmbeddingUnavailable


CORPUS = {"a": "SELECT revenue FROM sales", "b": "SELECT refunds FROM returns"}
QUERIES = {"q": "revenue sales", "r": "refunds returns"}
QRELS = {"q": {"a": 1}, "r": {"b": 1}}


class Vectors:
    version = "controlled-external-test-only"
    def embed(self, texts, task, timeout=10):
        return [[1., 0.] if "revenue" in t else [0., 1.] for t in texts]


def test_external_bm25_uses_full_corpus_and_deterministic_query_subset():
    report = evaluate_external(CORPUS, QUERIES, QRELS, limit=1)
    assert report["corpus_documents"] == 2
    assert report["evaluated_queries"] == 1
    assert report["query_ids"] == evaluate_external(CORPUS, QUERIES, QRELS, limit=1)["query_ids"]
    assert report["modes"]["bm25"]["metrics"]["by_k"]["10"]["ndcg"] == 1
    assert report["modes"]["vector"]["status"] == "untested"
    assert report["sql_executed"] is False


def test_controlled_embeddings_cannot_be_presented_as_live_evidence():
    report = evaluate_external(CORPUS, QUERIES, QRELS, embedder=Vectors(), embedding_source="controlled")
    assert report["semantic_quality"] == "not_evaluated_controlled_vectors_only"
    assert report["modes"]["vector"]["metrics"]["by_k"]["1"]["recall"] == 1
    assert report["modes"]["bm25_vector_rrf"]["metrics"]["by_k"]["1"]["recall"] == 1


def test_external_missing_reference_refused_before_embedding():
    class MustNotCall:
        version = "never"
        def embed(self, *args, **kwargs):
            raise AssertionError("Invalid labels must fail before paid calls")
    with pytest.raises(ValueError, match="reference"):
        evaluate_external(CORPUS, QUERIES, {"q": {"missing": 1}}, embedder=MustNotCall(), embedding_source="controlled")


def test_external_provider_failure_does_not_score_bm25_as_vector():
    class Unavailable(Vectors):
        def embed(self, *args, **kwargs):
            raise EmbeddingUnavailable()
    report = evaluate_external(CORPUS, QUERIES, QRELS, embedder=Unavailable(), embedding_source="controlled")
    assert report["modes"]["bm25"]["status"] == "tested"
    assert report["modes"]["vector"]["status"] == "untested"
    assert report["modes"]["vector"]["metrics"] is None


def test_external_adapter_without_index_version_is_refused_before_paid_calls():
    class Unversioned:
        def embed(self, *args, **kwargs):
            pytest.fail('Unversioned adapter must fail before billing')
    with pytest.raises(ValueError, match='version'):
        evaluate_external(CORPUS, QUERIES, QRELS, embedder=Unversioned(), embedding_source='live')
