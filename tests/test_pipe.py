import asyncio
import importlib.util
import json
from pathlib import Path


def test_pipe_forwards_trusted_identity_and_persists_final_text(monkeypatch):
    spec = importlib.util.spec_from_file_location("retail_pipe", Path(__file__).parents[1] / "integrations/openwebui_pipe.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    sent, events = {}, []
    class Response:
        status_code = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def aiter_lines(self):
            for event, data in [("progress", {"stage": "query"}), ("result", {"mode": "fixture", "answer": "Grounded answer"})]:
                for line in ["event: " + event, "data: " + json.dumps(data), ""]:
                    yield line
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def stream(self, method, url, **kwargs):
            sent.update(kwargs); return Response()
    monkeypatch.setattr(module.httpx, "AsyncClient", Client)
    pipe = module.Pipe(); pipe.valves.ADAPTER_SECRET = "server-secret"
    async def emit(event): events.append(event)
    result = asyncio.run(pipe.pipe({"messages": [{"role": "user", "content": "Analyze sales"}], "user": "forged-bob"},
        __user__={"id": "trusted-alice"}, __chat_id__="trusted-chat", __message_id__='trusted-message', __event_emitter__=emit))
    assert result.startswith("Grounded answer\n\n---\n\n")
    assert "[**Give feedback**](/static/retail-learning.html?chat=trusted-chat&message=trusted-message)" in result
    assert "[**My preferences**](/static/retail-learning.html#preferences)" in result
    assert "server-secret" not in result
    assert sent["headers"]["X-Webui-User"] == "trusted-alice"
    assert sent["json"]["external_chat_id"] == "trusted-chat"
    assert sent["json"]["external_message_id"] == 'trusted-message'
    assert events[-1]["data"]["done"] is True
    assert any("Querying" in e["data"]["description"] for e in events)
    assert asyncio.run(pipe.pipe({}, __task__="title_generation")) == ""


def test_real_pipe_api_agent_storage_flow_and_cross_user_report_access(tmp_path, monkeypatch):
    """ASGI integration: actual Pipe, API, LangGraph, fixture SQL and SQLite."""
    import httpx
    from retail.api import create_app
    from retail.config import Settings
    spec = importlib.util.spec_from_file_location("retail_pipe_integrated", Path(__file__).parents[1] / "integrations/openwebui_pipe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = Settings(_env_file=None, retail_mode="fixture", embedding_provider="none",
        database_url=f"sqlite:///{tmp_path}/pipe.db", log_path=str(tmp_path / "events.jsonl"),
        adapter_secret="unit-adapter", webui_users_json='{"web-alice":"alice","web-bob":"bob"}',
        langfuse_public_key="", langfuse_secret_key="")
    app = create_app(config)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw:
        real_client(**kw, transport=httpx.ASGITransport(app=app)))
    pipe = module.Pipe()
    pipe.valves.API_URL = "http://retail-test"
    pipe.valves.ADAPTER_SECRET = "unit-adapter"
    events = []
    async def emit(event): events.append(event)
    async def turn(question, user="web-alice", chat="first-chat"):
        return await pipe.pipe({"messages":[{"role":"user","content":question}]},
            __user__={"id":user}, __chat_id__=chat, __event_emitter__=emit)
    async def workflow():
        import re
        answer = await turn("Create and save a monthly revenue report")
        assert "100.0" in answer and "110.0" in answer and "Action items" in answer
        rid = re.search(r"rep_[a-f0-9]{16}", answer).group()
        assert rid in await turn("list reports", chat="new-chat")
        opened = await turn("open report " + rid, chat="new-chat")
        assert "100.0" in opened
        assert "```html\n<!DOCTYPE html>" in opened
        embeds = [e["data"]["embeds"][0] for e in events if e["type"] == "embeds"]
        assert len(embeds) == 2 and "100.0" in embeds[-1] and rid in embeds[-1]
        before = len(embeds)
        assert rid not in await turn("list reports", user="web-bob", chat="bob-chat")
        assert "not accessible" in await turn("open report " + rid, user="web-bob", chat="bob-chat")
        assert len([e for e in events if e["type"] == "embeds"]) == before
        assert events[-1]["data"]["done"] is True
        assert any(e["data"]["description"] == "Finding analyst examples" for e in events)
    asyncio.run(workflow())


def test_embed_delivery_failure_keeps_saved_answer_and_artifact(monkeypatch):
    """Dropped supplementary UI must not rerun the backend or lose the answer."""
    import httpx
    spec = importlib.util.spec_from_file_location("retail_pipe_embed_failure", Path(__file__).parents[1] / "integrations/openwebui_pipe.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    calls = []
    def handle(request):
        calls.append(request)
        result = {"mode": "live", "answer": "Saved report rep_test", "outcome": "succeeded",
            "report_view": {"html": "<!DOCTYPE html><html><body>Report</body></html>", "preview_html": "<html><body>Preview</body></html>"}}
        return httpx.Response(200, text="event: result\ndata: " + json.dumps(result) + "\n\n")
    original = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: original(**kw, transport=httpx.MockTransport(handle)))
    pipe = module.Pipe(); pipe.valves.ADAPTER_SECRET = "unit-only"
    async def emit(event):
        if event["type"] == "embeds":
            raise RuntimeError("socket closed")
    result = asyncio.run(pipe.pipe({"messages": [{"role": "user", "content": "save report"}]},
        __user__={"id": "alice"}, __chat_id__="chat", __event_emitter__=emit))
    assert "Saved report rep_test" in result and "```html" in result
    assert len(calls) == 1
    assert json.loads(calls[0].content)["include_report_view"] is True


def test_report_library_links_are_same_origin_and_titles_are_escaped():
    spec = importlib.util.spec_from_file_location('retail_library_pipe', Path(__file__).parents[1] / 'integrations/openwebui_pipe.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    result = module.report_library([{'id': 'rep_123', 'title': '[unsafe](https://evil.test)\n<script>'}])
    assert '/?models=retail_assessment_pipe&q=Open%20saved%20report%20rep_123' in result
    assert '[unsafe](https://evil.test)' not in result
    assert '<script>' not in result
    assert 'review and send' in result
