from retail.agent import Agent
from retail.analytics import Analytics
from retail.config import Settings
from retail.security import PolicyError, principal_for
from retail.store import Store
import pytest


def test_create_and_save_report_in_one_turn_then_open_from_fresh_chat(tmp_path):
    config = Settings(database_url=f"sqlite:///{tmp_path}/state.db", log_path=str(tmp_path / "events.jsonl"))
    store = Store(config.database_url); alice = principal_for("alice", config)
    agent = Agent(config, store)
    result = agent.chat(alice, "Create and save a monthly revenue report")
    rid = result["management"]["report_id"]
    assert "Action items" in result["answer"]
    assert len(store.reports(alice)) == 1
    opened = agent.chat(alice, f"open report {rid}")
    assert opened["management"]["report_id"] == rid
    assert "Action items" in opened["answer"] and "100.0" in opened["answer"]
    assert opened["conversation_id"] != result["conversation_id"]


def test_result_byte_and_privacy_checks_precede_model_context(tmp_path):
    config = Settings(max_result_bytes=1024)
    analytics = Analytics(config); alice = principal_for("alice", config)
    with pytest.raises(PolicyError, match="size"):
        analytics.execute("SELECT '" + "a" * 1100 + "' AS value FROM products", alice)
    with pytest.raises(PolicyError, match="disclosure"):
        analytics.execute("SELECT 'person@example.com' AS value FROM products", alice)


def test_oversized_model_context_stops_before_call(tmp_path):
    config = Settings(database_url=f"sqlite:///{tmp_path}/state.db", log_path=str(tmp_path / "events.jsonl"), max_context_chars=2000)
    class NoCall:
        def decide(self, *args): raise AssertionError("Model should not be invoked")
    result = Agent(config, Store(config.database_url), NoCall()).chat(principal_for("alice", config), "sales " + "x" * 3000)
    assert result["outcome"] == "budget_exhausted"
