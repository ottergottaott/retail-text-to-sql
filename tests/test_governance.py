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
