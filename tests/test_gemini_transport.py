"""Exercise the real Google SDK transport without contacting Google."""
import json

import httpx

from retail.config import Settings
from retail.model import GeminiModel


def test_direct_google_endpoint_key_and_structured_decision(monkeypatch):
    requests = []

    def send(client, request, **kwargs):
        requests.append(request)
        return httpx.Response(200, request=request, json={
            "candidates": [{"content": {"role": "model", "parts": [
                {"text": '{"action":"clarify","text":"Which period?","format":"tables","depth":"standard"}'}
            ]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 8, "totalTokenCount": 20},
        })

    monkeypatch.setattr(httpx.Client, "send", send)
    config = Settings(_env_file=None, gemini_api_key="transport-test-key",
                      gemini_model="transport-test-model")
    decision, usage = GeminiModel(config).decide({"question": "Show revenue"}, 10)
    assert decision.action == "clarify"
    assert usage["total_tokens"] == 20
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == (
        "https://generativelanguage.googleapis.com/v1beta/models/transport-test-model:generateContent")
    assert request.headers["x-goog-api-key"] == "transport-test-key"
    body = json.loads(request.content)
    assert "transport-test-key" not in request.content.decode()
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    schema = body["generationConfig"].get("responseSchema") or body["generationConfig"]["responseJsonSchema"]
    assert "action" in schema["properties"]
    assert "query" in schema["properties"]["action"]["enum"]
