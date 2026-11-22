import json
from retail.agent import Agent
from retail.config import Settings
from retail.model import Decision
from retail.security import principal_for
from retail.store import Store


def test_model_receives_trusted_defaults_brand_scope_and_current_override(tmp_path):
    config = Settings(database_url=f'sqlite:///{tmp_path}/db', log_path=str(tmp_path/'events'),
        brand_access_json='{"alice":{"role":"manager","brands":["North"]}}', churn_window_days=120)
    contexts = []
    class Model:
        def decide(self, context, remaining_seconds):
            contexts.append(context)
            return Decision(action='clarify', text='Which as-of date?'), {}
    Agent(config, Store(config.database_url), Model()).chat(principal_for('alice', config),
        'For this question use churn as no completed purchase in 60 days')
    context = contexts[0]
    assert context['business_defaults']['churn_window_days'] == 120
    assert context['business_defaults']['revenue_statuses'] == ['Complete']
    assert context['business_defaults']['user_analytical_override_allowed'] is True
    assert context['privacy_policy']['minimum_distinct_customers'] == 5
    assert context['execution_scope']['brands'] == ['North']
    assert '60 days' in context['question']


def test_demographic_denial_is_terminal_before_results_reach_model(tmp_path):
    config = Settings(database_url=f'sqlite:///{tmp_path}/db', log_path=str(tmp_path/'events'))
    contexts = []
    class Model:
        def decide(self, context, remaining_seconds):
            contexts.append(context)
            return Decision(action='query', sql='SELECT customer_key, state FROM users'), {}
    result = Agent(config, Store(config.database_url), Model()).chat(principal_for('alice', config),
        'Show individual customer locations')
    assert result['outcome'] == 'denied'
    assert result['evidence'] == []
    assert len(contexts) == 1
    assert 'California' not in json.dumps(contexts)


def test_no_sensitive_raw_fields_in_bound_query_projections():
    from retail.analytics import physical_sources
    from sqlglot import parse_one, exp
    # Check exposed SELECT expressions, not the raw source field used inside the
    # trusted hash; pseudonym generation necessarily reads the raw database ID.
    for name, source in physical_sources(Settings()).items():
        tree = parse_one(source, read='bigquery')
        exposed = {node.alias_or_name for node in tree.expressions}
        assert not exposed & {'first_name','last_name','email','street_address','postal_code',
            'latitude','longitude','ip_address','user_id','customer_id'}


def test_demographic_answer_cannot_mix_separate_total_queries(tmp_path):
    config = Settings(database_url=f'sqlite:///{tmp_path}/db', log_path=str(tmp_path/'events'))
    decisions = iter([
        Decision(action='query', sql='SELECT COUNT(DISTINCT customer_key) AS n FROM order_items'),
        Decision(action='query', sql='SELECT state, COUNT(*) AS n FROM users GROUP BY state'),
        Decision(action='answer', text='Must not reach this answer')])
    class Model:
        def decide(self, context, remaining_seconds): return next(decisions), {}
    result = Agent(config, Store(config.database_url), Model()).chat(principal_for('alice', config),
        'Compare the total and demographic groups')
    assert result['outcome'] == 'denied'
    assert len(result['evidence']) == 1
