"""Regressions reproduced during the first Superpowers review."""
import subprocess
import sys

import pytest

from retail.agent import Agent
from retail.analytics import Analytics, QueryUnavailable
from retail.config import Settings
from retail.model import Decision
from retail.security import Principal, principal_for
from retail.store import Store


def test_fixture_refuses_execution_after_deadline():
    config = Settings(_env_file=None)
    with pytest.raises(QueryUnavailable, match="budget"):
        Analytics(config).execute("SELECT COUNT(*) AS n FROM products",
            principal_for("alice", config), remaining_seconds=0)


def test_fixture_interrupts_nonterminating_query():
    # Keep the regression itself bounded even when cancellation is broken.
    code = '''
from retail.analytics import Analytics, QueryUnavailable
from retail.config import Settings
from retail.security import principal_for
config = Settings(_env_file=None)
try:
    Analytics(config).execute(
        "WITH RECURSIVE t AS (SELECT id FROM products UNION ALL SELECT id FROM t) SELECT SUM(id) AS n FROM t",
        principal_for("alice", config), remaining_seconds=1)
except QueryUnavailable:
    print("bounded-query-stopped")
else:
    raise AssertionError("Infinite query unexpectedly completed")
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
        text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "bounded-query-stopped"


def test_fresh_analytical_answer_requires_query_evidence(tmp_path):
    config = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/state.db",
        log_path=str(tmp_path / "events.jsonl"))

    class UnsupportedAnswer:
        def decide(self, context, remaining_seconds):
            return Decision(action="answer", text="Revenue is 999999. The query completed."), {}

    store = Store(config.database_url)
    alice = principal_for("alice", config)
    result = Agent(config, store, model=UnsupportedAnswer()).chat(alice, "What is revenue for my products?")
    assert result["outcome"] != "succeeded"
    assert "999999" not in result["answer"]
    assert "last_analysis" not in store.get("conversation", "alice", result["conversation_id"])["body"]


def test_sensitive_column_attempt_is_terminal_without_sql_repair(tmp_path):
    config = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/state.db",
        log_path=str(tmp_path / "events.jsonl"))

    class SensitiveThenSafe:
        calls = 0

        def decide(self, context, remaining_seconds):
            self.calls += 1
            if self.calls == 1:
                return Decision(action="query", sql="SELECT email FROM users"), {}
            if self.calls == 2:
                return Decision(action="query", sql="SELECT COUNT(*) AS n FROM users"), {}
            return Decision(action="answer", text="The query succeeded."), {}

    model = SensitiveThenSafe()
    result = Agent(config, Store(config.database_url), model=model).chat(
        principal_for("alice", config), "Analyze my customers")
    assert result["outcome"] == "denied"
    assert model.calls == 1
    assert result["evidence"] == []


@pytest.mark.parametrize("products,allowed", [((1, 2), True), ((1,), False)])
def test_followup_answer_can_use_only_authorized_previous_analysis(tmp_path, products, allowed):
    config = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/state.db",
        log_path=str(tmp_path / "events.jsonl"))
    store = Store(config.database_url)
    initial = Agent(config, store).chat(principal_for("alice", config), "monthly revenue")

    class Followup:
        def decide(self, context, remaining_seconds):
            return Decision(action="answer", text="The previous analysis showed revenue of 100 and 110."), {}

    result = Agent(config, store, model=Followup()).chat(Principal("alice", products),
        "Summarize the previous analysis", initial["conversation_id"])
    assert (result["outcome"] == "succeeded") is allowed
    if not allowed:
        assert "revenue of 100 and 110" not in result["answer"]


def test_empty_final_answer_cannot_complete_or_save_analysis(tmp_path):
    config = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/state.db",
                      log_path=str(tmp_path / "events.jsonl"))
    decisions = iter([Decision(action="query", sql="SELECT COUNT(*) AS n FROM products"),
                      Decision(action="save_report", title="Must not save empty analysis"),
                      Decision(action="answer", text="   ")])
    class EmptyAnswer:
        def decide(self, context, remaining_seconds):
            return next(decisions), {}
    store = Store(config.database_url)
    alice = principal_for("alice", config)
    result = Agent(config, store, model=EmptyAnswer()).chat(alice, "Count my products and save the analysis")
    assert result["outcome"] == "failed"
    assert not store.reports(alice)
    assert "last_analysis" not in store.get("conversation", "alice", result["conversation_id"])["body"]
