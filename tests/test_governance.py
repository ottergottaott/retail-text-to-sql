import pytest
from retail.config import Settings
from retail.store import Store
from retail.governance import Governance
from retail.knowledge import Knowledge
from retail.security import PolicyError, principal_for
from retail.agent import Agent
from retail.model import Decision


def test_reviewed_improvement_and_persona_refresh(tmp_path):
    config = Settings(database_url=f"sqlite:///{tmp_path}/review.db", log_path=str(tmp_path / "events.jsonl"))
    store = Store(config.database_url); governance = Governance(config, store)
    alice, bob = [principal_for(user, config) for user in ["alice", "bob"]]
    conversation = store.conversation(alice)
    store.append(alice, conversation, "Count my authorized products", "Please clarify.", "trace-one")
    feedback = governance.feedback(alice, conversation, "trace-one", "Use the products table to count authorized products", "correction")
    trio = {"id": "authorized-product-count", "question": "Count my authorized products", "tags": ["count", "products", "authorized"],
        "sql": "SELECT COUNT(*) AS products FROM products", "report": "Count the authorized product catalogue; do not infer sold units from catalogue size.",
        "scope": "shared", "schema_version": "safe-v1", "origin": "synthetic reviewed demonstration"}
    candidate = governance.candidate("alice", feedback, trio)
    knowledge = Knowledge(store)
    assert not any(t["id"] == trio["id"] for t in knowledge.retrieve(trio["question"], alice))
    failed = governance.review(candidate, "analyst-demo", [{"name": "wrong oracle", "user": "alice", "expected_rows": [{"products": 999}]}])
    assert failed["published"] is False
    assert not any(t["id"] == trio["id"] for t in knowledge.published())
    passed = governance.review(candidate, "analyst-demo", [
        {"name": "Alice catalogue", "user": "alice", "expected_rows": [{"products": 2}]},
        {"name": "Bob catalogue", "user": "bob", "expected_rows": [{"products": 1}]},
    ])
    assert passed["status"] == "published"
    assert any(t["id"] == trio["id"] for t in knowledge.retrieve(trio["question"], alice))
    assert store.get("evaluation", "system", passed["evaluation_id"])["body"]["verdict"] == "pass"
    with pytest.raises(PolicyError):
        governance.feedback(bob, conversation, "trace-one", "bad", "helpful")
    class Inspect:
        contexts = []
        def decide(self, context, remaining_seconds):
            self.contexts.append(context)
            return Decision(action="clarify", text="Which metric?"), {}
    model = Inspect(); agent = Agent(config, store, model)
    agent.chat(alice, "Analyze sales")
    governance.persona("Use concise, plain business language.", "analyst-demo")
    agent.chat(alice, "Analyze sales")
    assert model.contexts[0]["persona"]["version"] == 0
    assert model.contexts[1]["persona"]["version"] == 1


def test_user_preferences_reach_model_and_rendered_evidence(tmp_path):
    config = Settings(database_url=f"sqlite:///{tmp_path}/prefs.db", log_path=str(tmp_path / "events.jsonl"))
    store = Store(config.database_url); alice = principal_for("alice", config)
    store.preference("alice", "bullets", "concise")
    response = Agent(config, store).chat(alice, "monthly revenue")
    assert "- month:" in response["answer"]
    assert "| month |" not in response["answer"]
    assert store.profile("bob")["format"] == "tables"


@pytest.mark.parametrize("via_feedback", [False, True])
def test_trio_publication_keeps_original_pii_but_model_copies_are_sanitized(tmp_path, via_feedback):
    config = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/publication.db",
                      log_path=str(tmp_path / "events.jsonl"))
    store = Store(config.database_url)
    alice = principal_for("alice", config)
    trio = {"id": "catalog-contact-example", "question": "Count catalog products for John Smith",
            "sql": "SELECT COUNT(*) AS products FROM products",
            "report": "Catalog contact John Smith: john@example.com, +1 212 555 0199, 192.0.2.12.",
            "tags": ["catalog", "products"], "scope": "shared", "schema_version": "safe-v1",
            "origin": "synthetic privacy regression"}

    class Embeddings:
        version = "test-only"
        def __init__(self): self.payloads = []
        def embed(self, texts, task, **kwargs):
            self.payloads.extend(texts)
            return [[1., 0.] for _ in texts]

    try:
        knowledge = Knowledge(store)
        if via_feedback:
            governance = Governance(config, store)
            conversation = store.conversation(alice)
            store.append(alice, conversation, "Count catalog products", "Clarify", "privacy-trace")
            feedback = governance.feedback(alice, conversation, "privacy-trace", "Use catalog count", "correction")
            candidate = governance.candidate("alice", feedback, trio)
            assert store.get("candidate", "system", candidate)["body"]["trio"] == trio
            result = governance.review(candidate, "local-reviewer", [
                {"name": "catalog count", "user": "alice", "expected_rows": [{"products": 2}]}])
            assert result["status"] == "published"
        else:
            knowledge.publish(trio, "local-reviewer", {"verdict": "pass", "cases": [{"passed": True}]})
        saved = next(t for t in knowledge.published() if t["id"] == trio["id"])
        assert all(saved[key] == value for key, value in trio.items())
        embedder = Embeddings()
        knowledge = Knowledge(store, embedder)
        knowledge.index()
        returned = knowledge.retrieve("catalog products", alice, k=10)
        copy = next(t for t in returned if t["id"] == trio["id"])
        assert set(trio) <= set(copy)
        payload = str(embedder.payloads) + str(copy)
        for private in ["John Smith", "john@example.com", "+1 212 555 0199", "192.0.2.12"]:
            assert private not in payload
        # Indexing/retrieval never rewrite the stored original.
        assert next(t for t in knowledge.published() if t["id"] == trio["id"])["report"] == trio["report"]
    finally:
        store.engine.dispose()


def test_original_question_is_used_only_for_local_retrieval(tmp_path):
    config = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/retrieval.db",
                      log_path=str(tmp_path / "events.jsonl"))
    store = Store(config.database_url)
    question = "personalpha@example.com"
    trio = {"id": "original-local-query", "version": 1, "status": "published",
            "schema_version": "safe-v1", "scope": "shared", "question": question,
            "report": "Count catalog products", "tags": [],
            "sql": "SELECT COUNT(*) AS products FROM products"}

    class InspectModel:
        contexts = []
        def decide(self, context, remaining_seconds):
            self.contexts.append(context)
            return Decision(action="clarify", text="Which metric?"), {}

    try:
        store.put("trio", "system", trio)
        alice = principal_for("alice", config)
        knowledge = Knowledge(store)
        # Only the original email tokens overlap. Sanitizing before lexical
        # ranking loses this match; external/model copies must still be masked.
        selected = knowledge.retrieve(question, alice)
        assert [t["id"] for t in selected] == [trio["id"]]
        assert question not in str(selected)
        model = InspectModel()
        agent = Agent(config, store, model)
        seen = []
        original_retrieve = agent.knowledge.retrieve
        def retrieve(raw_question, *args, **kwargs):
            seen.append(raw_question)
            return original_retrieve(raw_question, *args, **kwargs)
        agent.knowledge.retrieve = retrieve
        result = agent.chat(alice, question)
        assert seen == [question]
        assert model.contexts and question not in str(model.contexts)
        assert question not in str(result)
        assert question not in (tmp_path / "events.jsonl").read_text()
    finally:
        store.engine.dispose()
