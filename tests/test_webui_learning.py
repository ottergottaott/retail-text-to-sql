import asyncio
import importlib.util
from pathlib import Path
import httpx
from pydantic import BaseModel
from test_webui_report_library import extension


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,Path('integrations')/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_learning_proxy_auth_allowlists_and_sanitized_failures(monkeypatch):
    # Reuse only the mocked native verified-user dependency from the Reports tests.
    extension(monkeypatch)
    module=load('learning_event','openwebui_learning_event.py')
    from fastapi import FastAPI
    event=module.Event()
    async def configuration(id):return event.Valves(API_URL='http://backend',ADAPTER_SECRET='private-adapter')
    event.configuration=configuration
    app=FastAPI()
    asyncio.run(event.event({},__event_name__='system.startup.completed',__app__=app,__id__='learning'))
    requests=[]
    def handler(request):
        requests.append(request)
        if request.url.path.endswith('feedback-target'):
            return httpx.Response(200,json={'question':'Original question','answer':'Actual answer','revision':'rev1','secret':'do not forward'})
        if request.url.path.endswith('feedback'):
            return httpx.Response(200,json={'feedback_id':'fee_123','status':'unreviewed','secret':'do not forward'})
        return httpx.Response(503,text='raw private diagnostic')
    real=httpx.AsyncClient
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handler)))
    async def check():
        async with real(transport=httpx.ASGITransport(app=app),base_url='http://webui') as c:
            path='/api/retail-learning/feedback-target'
            params={'external_chat_id':'chat','external_message_id':'message'}
            assert (await c.get(path,params=params)).status_code==401
            response=await c.get(path,params=params,headers={'Authorization':'Bearer session','X-Webui-User':'bob'})
            assert response.json()=={'question':'Original question','answer':'Actual answer','revision':'rev1'}
            assert requests[-1].headers['X-Webui-User']=='verified-alice'
            response=await c.post('/api/retail-learning/feedback',headers={'Authorization':'Bearer session'},json={**params,'revision':'rev1','rating':'helpful'})
            assert response.json()=={'feedback_id':'fee_123','status':'unreviewed'}
            assert response.headers['Cache-Control']=='no-store'
            response=await c.get('/api/retail-learning/preferences',headers={'Authorization':'Bearer session'})
            assert response.status_code==503 and 'private diagnostic' not in response.text
    asyncio.run(check())


def test_feedback_action_uses_only_encoded_message_reference():
    module=load('feedback_action','openwebui_feedback_action.py')
    calls=[]
    async def invoke(event):calls.append(event)
    asyncio.run(module.Action().action({'chat_id':'chat-123','id':'message-123'},__user__={'id':'alice'},__event_call__=invoke))
    code=calls[0]['data']['code']
    assert 'retail-learning.html' in code and 'message-123' in code and 'chat-123' in code
    assert 'trace_id' not in code and 'token' not in code


def test_automatic_learning_proxy_exposes_only_owned_status_and_tone_controls(monkeypatch):
    extension(monkeypatch)
    module=load('automatic_learning_event','openwebui_learning_event.py')
    from fastapi import FastAPI
    event=module.Event()
    async def configuration(id):return event.Valves(API_URL='http://backend',ADAPTER_SECRET='private-adapter')
    event.configuration=configuration
    app=FastAPI()
    asyncio.run(event.event({},__event_name__='system.startup.completed',__app__=app,__id__='learning'))
    seen=[]
    def handler(request):
        seen.append(request)
        if request.url.path.startswith('/feedback/'):
            return httpx.Response(200,json={'feedback_id':'fee_123','status':'published','reason':'','trio_id':'learned-abc','source':{'secret':'hidden'}})
        if request.method=='POST':return httpx.Response(200,json={'job_id':'aut_123','status':'pending','secret':'hidden'})
        return httpx.Response(200,json={'tone':'Professional','version':1,'can_edit':True,'versions':[],'secret':'hidden'})
    real=httpx.AsyncClient
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handler)))
    async def check():
        async with real(transport=httpx.ASGITransport(app=app),base_url='http://webui') as c:
            headers={'Authorization':'Bearer session'}
            response=await c.get('/api/retail-learning/feedback/fee_123',headers=headers)
            assert response.status_code==200 and response.json()['status']=='published'
            assert 'source' not in response.json()
            response=await c.post('/api/retail-learning/organization/tone',headers=headers,json={'tone':'Professional'})
            assert response.json()=={'job_id':'aut_123','status':'pending'}
            assert seen[-1].headers['X-Webui-User']=='verified-alice'
            response=await c.post('/api/retail-learning/organization/tone',headers=headers,json={'tone':'Professional','role':'ceo'})
            assert response.status_code==422
            response=await c.get('/api/retail-learning/organization/tone',headers=headers)
            assert 'secret' not in response.json() and response.json()['can_edit']
    asyncio.run(check())
