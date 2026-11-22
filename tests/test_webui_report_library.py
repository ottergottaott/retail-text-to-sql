"""The extension authenticates in WebUI and never trusts a browser-supplied user ID."""
import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request


def extension(monkeypatch):
    async def verified(request: Request):
        if request.headers.get('Authorization') != 'Bearer session':
            raise HTTPException(401, 'Unauthorized')
        return SimpleNamespace(id='verified-alice')
    auth = types.ModuleType('open_webui.utils.auth')
    auth.get_verified_user = verified
    monkeypatch.setitem(sys.modules, 'open_webui.utils.auth', auth)
    spec = importlib.util.spec_from_file_location('report_library_event', Path('integrations/openwebui_reports_event.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    event = module.Event()
    event.valves.API_URL = 'http://retail'
    event.valves.ADAPTER_SECRET = 'private-adapter'
    async def configuration(function_id): return event.valves
    event.configuration = configuration
    app = FastAPI()
    asyncio.run(event.event({}, __event_name__='system.startup.completed', __app__=app, __id__='library'))
    return module, event, app


def test_proxy_verified_identity_auth_and_html_policy(monkeypatch):
    module, event, app = extension(monkeypatch)
    requests = []
    def handle(request):
        requests.append(request)
        if request.url.path.endswith('/html'):
            return httpx.Response(200, text='<html>Private report</html>')
        return httpx.Response(200, json=[{'id':'rep_123','title':'Title','created':123}])
    real = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kw: real(**kw, transport=httpx.MockTransport(handle)))
    async def check():
        async with real(transport=httpx.ASGITransport(app=app), base_url='http://webui') as c:
            assert (await c.get('/api/retail-reports')).status_code == 401
            assert not requests
            r=await c.get('/api/retail-reports',headers={'Authorization':'Bearer session','X-Webui-User':'forged-bob'})
            assert r.json()[0]['id']=='rep_123'
            assert requests[-1].headers['X-Webui-User']=='verified-alice'
            assert requests[-1].headers['Authorization']=='Bearer private-adapter'
            r=await c.get('/api/retail-reports/rep_123/html',headers={'Authorization':'Bearer session'})
            assert r.status_code==200 and r.headers['Cache-Control']=='no-store'
            assert "default-src 'none'" in r.headers['Content-Security-Policy']
            assert 'private-adapter' not in r.text
            assert (await c.get('/api/retail-reports/invalid/html',headers={'Authorization':'Bearer session'})).status_code==404
    asyncio.run(check())


def test_proxy_failure_is_sanitized_and_registration_idempotent(monkeypatch):
    module, event, app=extension(monkeypatch)
    count=len(app.routes)
    asyncio.run(event.event({'subject':{'id':'library'}}, __event_name__='function.enable_started', __app__=app,__id__='library'))
    assert len(app.routes)==count
    def handle(request):
        return httpx.Response(403,text='secret provider diagnostics')
    real=httpx.AsyncClient
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handle)))
    async def check():
        async with real(transport=httpx.ASGITransport(app=app),base_url='http://webui') as c:
            r=await c.get('/api/retail-reports/rep_other/html',headers={'Authorization':'Bearer session'})
            assert r.status_code==403 and 'secret' not in r.text
    asyncio.run(check())


def test_native_action_opens_only_fixed_same_origin_library():
    spec=importlib.util.spec_from_file_location('report_action',Path('integrations/openwebui_reports_action.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    calls=[]
    async def invoke(event):calls.append(event)
    asyncio.run(module.Action().action({},__user__={'id':'alice'},__event_call__=invoke))
    assert calls[0]['type']=='execute'
    assert '/static/retail-reports.html' in calls[0]['data']['code']
    assert 'token' not in str(calls)


def test_proxy_inserts_before_spa_and_handles_unavailable_backend(monkeypatch):
    module, event, app = extension(monkeypatch)
    # A real WebUI ends with a mount at ''. The proxy must precede that fallback.
    second = FastAPI(); second.mount('/', FastAPI())
    asyncio.run(event.event({}, __event_name__='system.startup.completed', __app__=second, __id__='library'))
    assert [getattr(r,'path',None) for r in second.routes].index('/api/retail-reports') < [getattr(r,'path',None) for r in second.routes].index('')
    def handle(request): raise httpx.ConnectError('raw secret diagnostic',request=request)
    real = httpx.AsyncClient
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handle)))
    async def check():
        async with real(transport=httpx.ASGITransport(app=app),base_url='http://webui') as c:
            r=await c.get('/api/retail-reports',headers={'Authorization':'Bearer session'})
            assert r.status_code==503 and 'raw secret' not in r.text
    asyncio.run(check())
