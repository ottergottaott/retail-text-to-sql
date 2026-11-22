"""Learning feedback must resolve an actual owned response, not a supplied trace."""
import json
import pytest
from fastapi.testclient import TestClient
from retail.api import create_app
from retail.config import Settings


@pytest.fixture
def learning(tmp_path):
    config=Settings(_env_file=None,retail_mode='fixture',embedding_provider='none',
        database_url=f'sqlite:///{tmp_path}/learning.db',log_path=str(tmp_path/'events.jsonl'),
        adapter_secret='unit-adapter',webui_users_json='{"web-alice":"alice","web-bob":"bob"}',
        langfuse_public_key='',langfuse_secret_key='')
    app=create_app(config)
    return TestClient(app),config,app.state.store


ALICE={'Authorization':'Bearer unit-adapter','X-Webui-User':'web-alice'}
BOB={'Authorization':'Bearer unit-adapter','X-Webui-User':'web-bob'}
TARGET={'external_chat_id':'chat-a','external_message_id':'answer-a'}


def turn(client):
    response=client.post('/chat',headers=ALICE,json={'message':'schema',**TARGET})
    assert response.status_code==200
    return response.json()


def target(client,headers=ALICE):
    return client.get('/webui/feedback-target',headers=headers,params=TARGET)


def test_response_mapping_and_rating_only_feedback(learning):
    client,config,store=learning
    result=turn(client)
    response=target(client)
    assert response.status_code==200
    snapshot=response.json()
    assert snapshot['question']=='schema'
    assert snapshot['answer'] in result['answer']
    assert 'trace_id' not in snapshot and 'conversation_id' not in snapshot
    feedback=client.post('/webui/feedback',headers=ALICE,json={**TARGET,
        'revision':snapshot['revision'],'rating':'helpful'})
    assert feedback.status_code==200 and feedback.json()['status']=='unreviewed'
    record=store.get('feedback','alice',feedback.json()['feedback_id'])['body']
    assert record['trace_id']==result['trace_id']
    assert record['conversation']==result['conversation_id']
    assert record['comment'] and record['status']=='unreviewed'


def test_feedback_scope_ownership_and_forged_trace(learning):
    client,config,store=learning
    turn(client)
    assert target(client,BOB).status_code==403
    snapshot=target(client).json()
    body={**TARGET,'revision':snapshot['revision'],'rating':'correction','comment':'Use item grain.'}
    assert client.post('/webui/feedback',headers=BOB,json=body).status_code==403
    assert client.post('/webui/feedback',headers=ALICE,json={**body,'trace_id':'forged'}).status_code==422
    config.entitlements_json='{"alice":[1],"bob":[3]}'
    assert target(client).status_code==403
    assert client.post('/webui/feedback',headers=ALICE,json=body).status_code==403


def test_regenerated_response_rejects_stale_feedback_and_cleans_comment(learning):
    client,config,store=learning
    turn(client); old=target(client).json()
    turn(client); new=target(client).json()
    assert old['revision']!=new['revision']
    body={**TARGET,'revision':old['revision'],'rating':'correction','comment':'Email analyst@example.com'}
    assert client.post('/webui/feedback',headers=ALICE,json=body).status_code==403
    body['revision']=new['revision']
    response=client.post('/webui/feedback',headers=ALICE,json=body)
    assert response.status_code==200
    record=store.get('feedback','alice',response.json()['feedback_id'])['body']
    assert 'analyst@example.com' not in record['comment']


def test_failed_regeneration_retires_previous_feedback_target(learning,monkeypatch):
    client,config,store=learning
    original=turn(client); old=target(client).json()
    # Unexpected agent failures can return a new trace without appending history.
    monkeypatch.setattr(client.app.state.agent,'chat',lambda *args,**kwargs:{
        **original,'trace_id':'failed-unpersisted-trace','outcome':'failed','answer':'Unable to complete.'})
    assert client.post('/chat',headers=ALICE,json={'message':'schema',**TARGET}).status_code==200
    assert target(client).status_code==403
    assert client.post('/webui/feedback',headers=ALICE,json={**TARGET,
        'revision':old['revision'],'rating':'helpful'}).status_code==403


def test_mapping_survives_history_window_and_preferences_survive_new_chats(learning):
    client,config,store=learning
    result=turn(client)
    conversation=store.get('conversation','alice',result['conversation_id'])['body']
    conversation['messages']=[]
    store.replace('conversation','alice',result['conversation_id'],conversation)
    snapshot=target(client).json()
    response=client.post('/webui/feedback',headers=ALICE,json={**TARGET,
        'revision':snapshot['revision'],'rating':'unhelpful'})
    assert response.status_code==200
    client.put('/preferences',headers=ALICE,json={'format':'bullets','depth':'concise'}).raise_for_status()
    next_turn=client.post('/chat',headers=ALICE,json={'message':'monthly revenue','external_chat_id':'new-chat'}).json()
    assert '- month:' in next_turn['answer'] and '| month |' not in next_turn['answer']
    restarted=TestClient(create_app(config))
    assert restarted.get('/preferences',headers=ALICE).json()['format']=='bullets'
    assert restarted.get('/preferences',headers=BOB).json()['format']=='tables'
