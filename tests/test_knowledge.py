import pytest
from retail.config import Settings
from retail.store import Store
from retail.knowledge import Knowledge, SEEDS
from retail.security import principal_for
from retail.embeddings import EmbeddingUnavailable


class Embeddings:
    """Controlled vectors verify fusion mechanics, not Gemini semantic quality."""
    version = "controlled-test-v1"

    def __init__(self):
        self.seen = []
        self.down = False

    def embed(self, texts, task, timeout=10):
        self.seen.extend(texts)
        if self.down:
            raise EmbeddingUnavailable()
        return [[1., 0.] if "monthly" in t.lower() or "takings" in t.lower() else [0., 1.] for t in texts]


@pytest.fixture
def setup(tmp_path):
    config = Settings(database_url=f"sqlite:///{tmp_path}/knowledge.db")
    embedder = Embeddings()
    return Knowledge(Store(config.database_url), embedder), embedder, principal_for("alice", config)


def test_semantic_candidate_without_lexical_overlap_and_index_persistence(setup):
    knowledge, embedder, alice = setup
    assert knowledge.retrieve("takings", alice) == []
    assert knowledge.index()["indexed"] == 3
    assert knowledge.index()["indexed"] == 0
    events = []
    found = knowledge.retrieve("takings", alice, emit=lambda stage, **facts: events.append(facts))
    assert found[0]["id"] == "monthly-revenue"
    assert events[-1]["retrieval_mode"] == "hybrid"
    embedder.down = True
    assert knowledge.retrieve("monthly revenue", alice, emit=lambda stage, **facts: events.append(facts))
    assert events[-1]["retrieval_mode"] == "lexical_fallback"


def test_latest_scope_cannot_resurrect_old_shared_version(setup):
    knowledge, embedder, alice = setup
    original = next(t for t in knowledge.published() if t["id"] == "monthly-revenue")
    knowledge.store.put("trio", "system", {**original, "version": 2, "scope": "products", "products": [3]})
    knowledge.index()
    result = knowledge.retrieve("monthly revenue", alice)
    assert all(t["id"] != "monthly-revenue" for t in result)
    # Out-of-scope documents are not sent to the query embedding provider.
    embedder.seen = []
    knowledge.retrieve("takings", alice)
    assert embedder.seen == ["takings"]


def test_schema_mismatch_and_unrelated_lexical_query(setup):
    knowledge, _, alice = setup
    assert knowledge.retrieve("weather forecast", alice) == []
    original = next(t for t in knowledge.published() if t["id"] == "monthly-revenue")
    knowledge.store.put("trio", "system", {**original, "version": 2, "schema_version": "removed-schema"})
    assert all(t["id"] != "monthly-revenue" for t in knowledge.retrieve("monthly revenue", alice))


def test_hybrid_rejects_lexical_matches_when_semantics_are_unrelated(setup):
    knowledge, embedder, alice = setup
    knowledge.index()
    embedder.embed = lambda texts, task, timeout=10: [[0., 0.] for text in texts]
    events = []
    assert knowledge.retrieve('monthly revenue weather forecast', alice,
        emit=lambda stage, **facts: events.append(facts)) == []
    assert events[-1]['relevance_gate'] == 'applied'
    assert events[-1]['lexical_rejected'] > 0
    assert events[-1]['retrieval_mode'] == 'hybrid'


def test_gate_keeps_lexical_rescue_below_strong_semantic_threshold(setup):
    import math
    knowledge, embedder, alice = setup
    knowledge.index()
    embedder.embed = lambda texts, task, timeout=10: [[0.62, math.sqrt(1-0.62**2)] for text in texts]
    assert any(t['id'] == 'monthly-revenue' for t in knowledge.retrieve('monthly revenue', alice, k=3))


def test_gate_excludes_unindexed_lexical_candidates_from_partial_index(setup):
    knowledge, embedder, alice = setup
    # Index the existing corpus, then publish a new lexical match with no vector.
    knowledge.index()
    original = next(t for t in knowledge.published() if t['id'] == 'monthly-revenue')
    knowledge.store.put('trio', 'system', {**original, 'version': 2})
    events = []
    result = knowledge.retrieve('monthly revenue', alice, k=3,
        emit=lambda stage, **facts: events.append(facts))
    assert all(t['id'] != 'monthly-revenue' for t in result)
    assert events[-1]['index_complete'] is False
    assert events[-1]['relevance_gate'] == 'applied'


def test_embedding_failure_preserves_explicitly_ungated_fallback(setup):
    knowledge, embedder, alice = setup
    knowledge.index()
    embedder.down = True
    events = []
    assert knowledge.retrieve('monthly revenue', alice,
        emit=lambda stage, **facts: events.append(facts))
    assert events[-1]['retrieval_mode'] == 'lexical_fallback'
    assert events[-1]['relevance_gate'] == 'unavailable'
