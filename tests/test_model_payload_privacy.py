"""Local PII boundary regressions: no provider calls or production data."""
import copy
import json
import pytest

from retail.security import PolicyError


def test_trio_copy_keeps_fields_and_original_while_removing_restricted_values():
    from retail.model_privacy import sanitize_payload
    trio = {
        'question': 'Compare purchases by John Smith at john.smith@example.com.',
        'sql': "SELECT COUNT(*) FROM users WHERE first_name='John' AND postal_code='90210'",
        'report': 'Customer 12345 lives at 123 Main Street. IP 2001:db8::1; coordinates 37.7749, -122.4194.',
        'tags': ['revenue', 'John Smith'],
        'nested': {'first_name': 'John', 'last_name': 'Smith', 'street_address': '123 Main Street',
                   'postal_code': '90210', 'latitude': 37.7749, 'longitude': -122.4194,
                   'customer_id': 12345, 'customer_key': 'a' * 64},
    }
    original = copy.deepcopy(trio)
    safe = sanitize_payload(trio, 'unit-secret')
    serialized = json.dumps(safe)
    for value in ['John', 'Smith', 'john.smith@example.com', '123 Main Street', '90210',
                  '2001:db8::1', '37.7749', '-122.4194', '12345']:
        assert value not in serialized
    assert trio == original and safe.keys() == trio.keys()
    assert safe['nested']['customer_key'] == 'a' * 64
    assert safe == sanitize_payload(safe, 'unit-secret')


def test_customer_pseudonyms_are_stable_and_secret_specific():
    from retail.model_privacy import sanitize_payload
    a = sanitize_payload({'customer_id': 12345}, 'one')
    assert a == sanitize_payload({'customer_id': 12345}, 'one')
    assert a != sanitize_payload({'customer_id': 12345}, 'two')


def test_aggregate_demographics_metrics_dates_and_schema_names_remain():
    from retail.model_privacy import sanitize_payload
    payload = {'rows': [{'state': 'California', 'country': 'United States', 'age_band': '30-39',
                         'customers': 5, 'revenue': 90210.0}],
               'sql': "SELECT state, COUNT(*) FROM users GROUP BY state",
               'question': 'Show monthly revenue since 2026-01-01.',
               'schema': 'first_name, last_name, email, postal_code'}
    assert sanitize_payload(payload, 'one') == payload


def test_detector_failure_stops_egress(monkeypatch):
    import retail.model_privacy as privacy
    def unavailable():
        raise RuntimeError('private detector diagnostic')
    monkeypatch.setattr(privacy, '_person_detector', unavailable)
    with pytest.raises(PolicyError, match='privacy') as error:
        privacy.sanitize_payload({'question': 'Revenue'}, 'one')
    assert 'private detector diagnostic' not in str(error.value)


@pytest.mark.parametrize('value', [
    'Contact John Smith at john@example.com or +1 (415) 555-0123.',
    'Street address: 123 Main Street, postal code: 90210.',
    'IP address: 192.168.1.2; IPv6: 2001:db8::1.',
    'Coordinates: 37.7749, -122.4194.',
    'customer_id=12345',
])
def test_sensitive_text_is_changed(value):
    from retail.model_privacy import sanitize_payload
    assert sanitize_payload(value, 'one') != value


def test_legacy_trio_index_and_retrieval_sanitize_without_rewriting_storage(tmp_path):
    from retail.knowledge import Knowledge, SEEDS
    from retail.store import Store
    from retail.security import Principal
    class Spy:
        version = 'mock-v1'
        seen = []
        def embed(self, texts, task, timeout=10):
            self.seen.extend(texts)
            return [[1., 0.] for _ in texts]
    store = Store(f'sqlite:///{tmp_path}/state.db')
    spy = Spy()
    knowledge = Knowledge(store, spy, privacy_secret='unit-secret')
    record = {**SEEDS[0], 'version': 2, 'schema_version': 'safe-v1',
              'question': 'Monthly revenue for John Smith',
              'report': 'John Smith lives at 123 Main Street; postal code: 90210.',
              'sql': "SELECT COUNT(*) FROM users WHERE first_name='John'",
              'reviewer': 'John Smith', 'evaluation': {'comment': 'john@example.com'}}
    key = store.put('trio', 'system', record)
    knowledge.index()
    found = knowledge.retrieve('monthly revenue John Smith', Principal('alice', (1,2)), k=3)
    outgoing = json.dumps([spy.seen, found])
    for raw in ['John', 'Smith', '123 Main Street', '90210', 'john@example.com']:
        assert raw not in outgoing
    assert any(t['id'] == record['id'] for t in found)
    assert store.get('trio', 'system', key)['body'] == record
    store.engine.dispose()


def test_generation_and_review_use_sanitized_copies(tmp_path):
    from retail.agent import Agent
    from retail.analytics import Analytics
    from retail.config import Settings
    from retail.model import Decision
    from retail.security import principal_for
    from retail.store import Store
    settings = Settings(_env_file=None, retail_mode='live', embedding_provider='none',
                        database_url=f'sqlite:///{tmp_path}/state.db', log_path=str(tmp_path/'trace.jsonl'))
    store = Store(settings.database_url)
    class Planner:
        seen = []
        def decide(self, context, remaining_seconds):
            self.seen.append(context)
            if len(self.seen) == 1:
                return Decision(action='query', sql='SELECT COUNT(*) AS n FROM products'), {}
            return Decision(action='answer', text='John Smith observed 2 products.'), {}
    class Reviewer:
        seen = []
        def decide(self, context, remaining_seconds):
            self.seen.append(context)
            return Decision(action='answer', text='2 products [q1].'), {}
    planner, reviewer = Planner(), Reviewer()
    agent = Agent(settings, store, model=planner, review_model=reviewer,
                  analytics=Analytics(settings.model_copy(update={'retail_mode':'fixture'})))
    result = agent.chat(principal_for('alice', settings), 'Count products for John Smith')
    assert result['outcome'] == 'succeeded'
    assert reviewer.seen
    assert 'John' not in json.dumps([planner.seen, reviewer.seen])
    assert '[REDACTED_PERSON]' in reviewer.seen[0]['report_review']['draft']
    store.engine.dispose()


def test_openai_compatible_transport_never_receives_raw_trio(monkeypatch):
    import httpx
    import retail.deepinfra as provider
    from retail.config import Settings
    captured = []
    real = httpx.Client
    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'choices':[{'message':{'content':'{"action":"clarify","text":"Which period?"}'}}]})
    monkeypatch.setattr(provider.httpx, 'Client', lambda **kw: real(**kw, transport=httpx.MockTransport(handler)))
    context = {'question':'revenue', 'trios':[{'question':'John Smith purchases', 'report':'john@example.com',
                                             'sql':"SELECT COUNT(*) FROM users WHERE postal_code='90210'"}]}
    provider.DeepInfraModel(Settings(_env_file=None)).decide(context, 10)
    sent = json.dumps(captured)
    assert 'John' not in sent and 'john@example.com' not in sent and '90210' not in sent
    assert context['trios'][0]['report'] == 'john@example.com'


def test_google_generation_and_embedding_boundaries(monkeypatch):
    from types import SimpleNamespace
    from google import genai
    from retail.config import Settings
    from retail.model import GeminiModel
    from retail.embeddings import GeminiEmbeddings
    calls = []
    class Models:
        def generate_content(self, **kw):
            calls.append(kw)
            return SimpleNamespace(text='{"action":"clarify","text":"Which period?"}', usage_metadata=None)
        def embed_content(self, **kw):
            calls.append(kw)
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[1., 0.])])
    class Client:
        def __init__(self, **kw): self.models = Models()
        def close(self): pass
    monkeypatch.setattr(genai, 'Client', Client)
    config = Settings(_env_file=None, gemini_api_key='unit-placeholder', gemini_model='unit-model')
    GeminiModel(config).decide({'question':'Revenue for John Smith'}, 10)
    GeminiEmbeddings(config).embed(['John Smith purchases at john@example.com'], 'RETRIEVAL_DOCUMENT')
    assert len(calls) == 2
    assert 'John' not in str(calls) and 'john@example.com' not in str(calls)


def test_policy_version_invalidates_previous_embedding_keys(tmp_path):
    import hashlib
    from retail.knowledge import Knowledge, SEEDS, document
    from retail.store import Store
    class Embedder:
        version = 'mock-v1'
    knowledge = Knowledge(Store(f'sqlite:///{tmp_path}/state.db'), Embedder())
    t = {**SEEDS[0], 'schema_version':'safe-v1'}
    old = {'id':t['id'], 'version':t['version'], 'schema':t['schema_version'],
           'model':'mock-v1', 'document':document(t)}
    old_key = 'emb_' + hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
    assert knowledge.vector_id(t) != old_key
    knowledge.store.engine.dispose()


def test_dynamic_keys_quoted_sql_fields_and_array_shape():
    from retail.model_privacy import sanitize_payload
    original = {'rows':[{'john@example.com': 10}], 'first_name':['John','Jane'],
                'sql': 'SELECT COUNT(*) FROM users WHERE "postal_code"=\'90210\''}
    safe = sanitize_payload(original, 'one')
    assert safe['first_name'] == ['[REDACTED_VALUE]', '[REDACTED_VALUE]']
    assert len(safe['rows'][0]) == 1
    assert 'john@example.com' not in json.dumps(safe) and '90210' not in json.dumps(safe)
    assert original['first_name'] == ['John','Jane']


def test_failed_detector_prevents_http_transport(monkeypatch):
    import retail.deepinfra as provider
    import retail.model_privacy as privacy
    from retail.config import Settings
    calls=[]
    def unavailable(): raise RuntimeError('detector down')
    monkeypatch.setattr(privacy, '_person_detector', unavailable)
    monkeypatch.setattr(provider.httpx, 'Client', lambda **kw: calls.append(kw))
    with pytest.raises(PolicyError):
        provider.DeepInfraModel(Settings(_env_file=None)).decide({'question':'John Smith revenue'}, 10)
    with pytest.raises(PolicyError):
        provider.DeepInfraEmbeddings(Settings(_env_file=None)).embed(['John Smith revenue'], 'RETRIEVAL_QUERY')
    assert calls == []
