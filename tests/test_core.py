import json
import pytest
from retail.config import Settings
from retail.store import Store
from retail.agent import Agent
from retail.analytics import Analytics, validate, bind, physical_sources, QueryError
from retail.model import Decision, ModelError
from retail.security import PolicyError, principal_for


@pytest.fixture
def config(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path}/state.db", log_path=str(tmp_path / "events.jsonl"))


def test_scoped_queries_and_row_cap(config):
    analytics = Analytics(config)
    alice, bob = [principal_for(user, config) for user in ["alice", "bob"]]
    sql = "SELECT product_id, SUM(sale_price) AS revenue FROM order_items GROUP BY product_id ORDER BY product_id"
    assert [r["product_id"] for r in analytics.execute(sql, alice)["rows"]] == [1, 2]
    assert [r["product_id"] for r in analytics.execute(sql, bob)["rows"]] == [3]
    limited = Analytics(config.model_copy(update={"max_rows": 1})).execute(sql, alice)
    assert limited["truncated"] and len(limited["rows"]) == 1


@pytest.mark.parametrize("sql", [
    "SELECT * FROM `bigquery-public-data.thelook_ecommerce.users`",
    "SELECT email FROM users", "DROP TABLE products", "SELECT * FROM products; SELECT * FROM users",
    "SELECT * FROM EXTERNAL_QUERY('connection', 'SELECT * FROM secrets')",
    "WITH orders AS (SELECT * FROM secret) SELECT * FROM orders",
    "SELECT SESSION_USER() FROM products",
])
def test_escape_denied(sql):
    with pytest.raises((PolicyError, QueryError)):
        validate(sql)


def test_nested_cte_sources_bound_not_cte_references(config):
    sql = "WITH products AS (SELECT product_id FROM order_items), nested AS (SELECT * FROM products) SELECT product_id FROM nested"
    tree, sources = validate(sql)
    assert [t.name for t in sources] == ["order_items"]
    output = bind(tree, physical_sources(config)).sql(dialect="bigquery")
    assert output.count("bigquery-public-data.thelook_ecommerce.order_items") == 1
    assert "UNNEST(@products)" in output
    assert "thelook_ecommerce.products" not in output


def test_report_confirmation_isolation_restart_replay(config):
    store = Store(config.database_url)
    a, b = [principal_for(user, config) for user in ["alice", "bob"]]
    con, other = store.conversation(a), store.conversation(a)
    rid = store.save_report(a, con, "Revenue", "Findings", {})
    proposal = store.propose_delete(a, con, phrase="revenue")
    assert len(store.reports(a)) == 1
    store = Store(config.database_url)  # proposal and reports survive process state
    with pytest.raises(PolicyError):
        store.confirm_delete(b, con, proposal["proposal_id"], True)
    with pytest.raises(PolicyError):
        store.confirm_delete(a, other, proposal["proposal_id"], True)
    assert store.confirm_delete(a, con, proposal["proposal_id"], True)["deleted"] == 1
    store.save_report(a, con, "New revenue", "Findings", {})
    assert store.confirm_delete(a, con, proposal["proposal_id"], True)["deleted"] == 0
    assert len(store.reports(a)) == 1
    assert store.reports(b) == []


def test_changed_target_and_cancellation(config):
    store = Store(config.database_url); a = principal_for("alice", config)
    con = store.conversation(a)
    rid = store.save_report(a, con, "Report", "Findings", {})
    proposal = store.propose_delete(a, con, current=True)
    body = store.get("report", a.user_id, rid)["body"]
    store.replace("report", a.user_id, rid, {**body, "content": "Revised findings"})
    with pytest.raises(PolicyError):
        store.confirm_delete(a, con, proposal["proposal_id"], True)
    assert len(store.reports(a)) == 1
    assert store.confirm_delete(a, con, proposal["proposal_id"], False)["status"] == "cancelled"
    assert len(store.reports(a)) == 1


def test_expired_proposal_preserves_reports(config):
    store = Store(config.database_url); a = principal_for("alice", config)
    con = store.conversation(a)
    store.save_report(a, con, "Report", "Findings", {})
    proposal = store.propose_delete(a, con, current=True)
    body = store.get("proposal", a.user_id, proposal["proposal_id"])["body"]
    store.replace("proposal", a.user_id, proposal["proposal_id"], {**body, "expires": 0})
    with pytest.raises(PolicyError, match="expired"):
        store.confirm_delete(a, con, proposal["proposal_id"], True)
    assert len(store.reports(a)) == 1


class Script:
    def __init__(self, decisions):
        self.decisions = iter(decisions)
        self.contexts = []

    def decide(self, context, remaining_seconds):
        self.contexts.append(context)
        return next(self.decisions), {"usage_source": "fixture"}


def test_agent_repairs_once_and_preserves_followup_context(config):
    model = Script([
        Decision(action="query", sql="SELECT missing FROM products"),
        Decision(action="query", sql="SELECT COUNT(*) AS n FROM products"),
        Decision(action="answer", text="Authorized product count is shown below."),
        Decision(action="clarify", text="Which comparison period?"),
    ])
    store = Store(config.database_url); a = principal_for("alice", config)
    agent = Agent(config, store, model)
    result = agent.chat(a, "Count my products")
    assert result["evidence"][0]["rows"] == [{"n": 2}]
    agent.chat(a, "Compare to the prior period", result["conversation_id"])
    assert model.contexts[-1]["history"][-1]["question"] == "Count my products"
    assert len([t for t in model.contexts[-2]["tools"] if t.get("error")]) == 1


def test_policy_stops_before_more_model_calls(config):
    model = Script([Decision(action="query", sql="SELECT * FROM `project.dataset.secret`")])
    agent = Agent(config, Store(config.database_url), model)
    response = agent.chat(principal_for("alice", config), "Analyze sales")
    assert not response["evidence"]
    assert "logical" in response["answer"]
    assert len(model.contexts) == 1


def test_sensitive_input_not_in_context_or_log(config):
    model = Script([Decision(action="clarify", text="Which metric?")])
    store = Store(config.database_url); agent = Agent(config, store, model)
    agent.chat(principal_for("alice", config), "Analyze sales for me test@example.com")
    assert "test@example.com" not in json.dumps(model.contexts)
    assert "test@example.com" not in open(config.log_path).read()
    assert "test@example.com" not in json.dumps(store.list("conversation", "alice"))


def test_budget_and_dependency_error(config):
    class Down:
        def decide(self, context, remaining_seconds):
            raise ModelError("Model unavailable; no result was inferred.")
    a = principal_for("alice", config)
    response = Agent(config, Store(config.database_url), Down()).chat(a, "Analyze sales")
    assert "unavailable" in response["answer"] and response["evidence"] == []
    limited = config.model_copy(update={"max_model_calls": 1})
    script = Script([Decision(action="query", sql="SELECT COUNT(*) AS n FROM products")])
    response = Agent(limited, Store(config.database_url), script).chat(a, "Count products")
    assert "budget" in response["answer"] and len(script.contexts) == 1


@pytest.mark.parametrize('predicate, expected', [
    ("status='Complete' AND product_id=1", 70.0),
    ("status='Complete' AND (product_id=1 OR product_id=2)", 210.0),
    ("NOT status!='Complete' AND product_id=2", 140.0),
])
def test_boolean_predicates_are_analytical_conditions_not_external_functions(config, predicate, expected):
    result = Analytics(config).execute(
        'SELECT SUM(sale_price) AS revenue FROM order_items WHERE ' + predicate,
        principal_for('alice', config))
    assert result['rows'] == [{'revenue': expected}]


def test_agent_supplies_sql_capabilities_before_generation(config):
    class CapabilityConsumer:
        def decide(self, context, remaining_seconds):
            if not context['tools']:
                capabilities = context['sql_capabilities']
                assert capabilities['dialect'] == 'bigquery'
                assert 'SUM' in capabilities['allowed_functions']
                assert 'COUNT_IF' not in capabilities['allowed_functions']
                assert capabilities['conditional_count_example'] == 'SUM(CASE WHEN condition THEN 1 ELSE 0 END)'
                return Decision(action='query', sql="SELECT SUM(CASE WHEN status='Returned' THEN 1 ELSE 0 END) AS returned FROM order_items WHERE status IN ('Complete','Returned') AND product_id=1"), {}
            return Decision(action='answer', text='There is one returned item for product 1.'), {}
    response = Agent(config, Store(config.database_url), CapabilityConsumer()).chat(
        principal_for('alice', config), 'Count returned finalized product items')
    assert response['outcome'] == 'succeeded'
    assert response['evidence'][0]['rows'] == [{'returned': 1}]
