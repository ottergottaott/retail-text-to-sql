import json
from fastapi.testclient import TestClient
from retail.agent import Agent
from retail.api import create_app
from retail.config import Settings
from retail.model import Decision, ModelError
from retail.security import Principal, principal_for
from retail.store import Store


def test_revoked_products_never_reenter_context_or_saved_report(tmp_path):
    config = Settings(database_url=f"sqlite:///{tmp_path}/state.db", log_path=str(tmp_path / "events.jsonl"))
    store = Store(config.database_url); alice = principal_for("alice", config)
    initial = Agent(config, store).chat(alice, "monthly revenue")
    class Inspect:
        contexts = []
        def decide(self, context, remaining_seconds):
            self.contexts.append(context)
            return Decision(action="save_report"), {}
    model = Inspect()
    narrowed = Principal("alice", (1,))
    result = Agent(config, store, model).chat(narrowed, "Save that analysis", initial["conversation_id"])
    assert model.contexts[0]["history"] == []
    assert "Access changed" in result["answer"] and result["outcome"] == "denied"
    assert store.reports(narrowed) == []


def test_trace_correlations_and_dependency_outcome(tmp_path):
    config = Settings(database_url=f"sqlite:///{tmp_path}/state.db", log_path=str(tmp_path / "events.jsonl"))
    store = Store(config.database_url); alice = principal_for("alice", config)
    response = Agent(config, store).chat(alice, "monthly revenue")
    events = [json.loads(line) for line in open(config.log_path)]
    assert {e["trace_id"] for e in events} == {response["trace_id"]}
    assert {e["request_id"] for e in events} == {response["trace_id"]}
    assert {e["turn_id"] for e in events} == {response["trace_id"]}
    assert all(e["conversation_id"] == response["conversation_id"] for e in events)
    assert next(e for e in events if e["stage"] == "model_context")["context_digest"]
    tools = [e for e in events if e["stage"] == "tool"]
    assert len(tools) == 2 and tools[0]["tool_call_id"] == tools[1]["tool_call_id"]
    assert tools[1]["outcome"] == "succeeded" and tools[1]["seconds"] >= 0
    assert events[-1]["stage"] == "response" and events[-1]["outcome"] == "succeeded"
    class Down:
        def decide(self, context, remaining_seconds): raise ModelError("Model unavailable")
    failed = Agent(config, store, Down()).chat(alice, "sales")
    assert failed["outcome"] == "dependency_error"
    assert json.loads(open(config.log_path).readlines()[-1])["outcome"] == "dependency_error"


def test_confirmation_requires_actual_boolean(tmp_path):
    config = Settings(database_url=f"sqlite:///{tmp_path}/state.db", log_path=str(tmp_path / "events.jsonl"))
    with TestClient(create_app(config)) as client:
        result = client.post("/reports/deletion-proposals/unknown/confirmation", headers={"Authorization": "Bearer alice-local-token"},
            json={"conversation_id": "unknown", "confirm": "yes"})
        assert result.status_code == 422
