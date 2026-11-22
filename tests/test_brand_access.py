import json
import pytest
from retail.analytics import Analytics
from retail.config import Settings
from retail.security import PolicyError, principal_for
from retail.store import Store
from retail.agent import Agent


def config_for(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path}/state.db", log_path=str(tmp_path / 'events.jsonl'),
        brand_access_json=json.dumps({'alice': {'role': 'manager', 'brands': ['North']},
            'bob': {'role': 'manager', 'brands': ['South']}, 'ceo': {'role': 'ceo'}}))


def test_manager_and_ceo_scope_actual_queries(tmp_path):
    config = config_for(tmp_path)
    analytics = Analytics(config)
    sql = 'SELECT brand, COUNT(*) AS n FROM products GROUP BY brand ORDER BY brand'
    # North includes product 4, absent from every legacy product-ID entitlement.
    assert analytics.execute(sql, principal_for('alice', config))['rows'] == [{'brand': 'North', 'n': 2}]
    assert analytics.execute(sql, principal_for('bob', config))['rows'] == [{'brand': 'South', 'n': 1}]
    assert analytics.execute(sql, principal_for('ceo', config))['rows'] == [
        {'brand': 'North', 'n': 2}, {'brand': 'South', 'n': 1}, {'brand': 'West', 'n': 1}]
    assert analytics.execute('SELECT SUM(sale_price) AS spend FROM order_items',
        principal_for('alice', config))['rows'] == [{'spend': 80.0}]


def test_brand_report_revocation_and_owner_are_enforced(tmp_path):
    config = config_for(tmp_path)
    store = Store(config.database_url)
    alice = principal_for('alice', config)
    conversation = store.conversation(alice)
    rid = store.save_report(alice, conversation, 'Revenue', 'North data', [])
    assert [r['id'] for r in store.reports(alice)] == [rid]
    changed = config.model_copy(update={'brand_access_json': '{"alice":{"role":"manager","brands":["South"]}}'})
    assert store.reports(principal_for('alice', changed)) == []
    assert store.reports(principal_for('ceo', config)) == []
    proposal = store.propose_delete(alice, conversation, ids=[rid])
    with pytest.raises(PolicyError):
        store.confirm_delete(principal_for('alice', changed), conversation, proposal['proposal_id'], True)


def test_brand_followup_retains_only_current_authorized_context(tmp_path):
    config = config_for(tmp_path)
    agent = Agent(config, Store(config.database_url))
    alice = principal_for('alice', config)
    first = agent.chat(alice, 'monthly revenue')
    assert first['completed_analysis']
    second = agent.chat(alice, 'save report', first['conversation_id'])
    assert second['management']['report_id']


def test_brand_scope_binds_bigquery_and_does_not_expand_to_manual_ids(tmp_path, monkeypatch):
    from google.cloud import bigquery
    from types import SimpleNamespace
    config = config_for(tmp_path).model_copy(update={'retail_mode': 'live', 'google_cloud_project': 'test'})
    calls = []
    class Client:
        def __init__(self, **kwargs): pass
        def close(self): pass
        def query(self, sql, job_config, **kwargs):
            calls.append((sql, job_config.to_api_repr()))
            return SimpleNamespace(total_bytes_processed=10, job_id='test', result=lambda **kw: [{'n': 2}])
    monkeypatch.setattr(bigquery, 'Client', Client)
    result = Analytics(config).execute('SELECT COUNT(*) AS n FROM order_items', principal_for('alice', config))
    assert result['rows'] == [{'n': 2}]
    sql, job = calls[-1]
    assert 'brand IN UNNEST(@brands)' in sql
    params = {p['name']: p['parameterValue'] for p in job['query']['queryParameters']}
    assert params['brands'] == {'arrayValues': [{'value': 'North'}]}
    assert params['products'] == {'arrayValues': []}
    assert params['all_brands']['value'] == 'false'


@pytest.mark.parametrize('entry', [None, {}, {'role': 'manager', 'brands': []},
    {'role': 'manager', 'brands': '*'}, {'role': 'admin'}, {'role': 'manager', 'brands': [1]}])
def test_brand_mapping_invalid_fails_closed(tmp_path, entry):
    config = config_for(tmp_path).model_copy(update={'brand_access_json': json.dumps({'alice': entry})})
    with pytest.raises(PolicyError):
        principal_for('alice', config)
