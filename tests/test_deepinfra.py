"""Controlled httpx.MockTransport checks for the DeepInfra adapters.

No live provider calls, real credentials or environment loading. The tests
monkeypatch the module's ``httpx.Client`` with a factory that installs a mock
transport while retaining the original client class.
"""
import json
from types import SimpleNamespace

import httpx
import pytest

import retail.deepinfra as deepinfra
from retail.embeddings import EmbeddingUnavailable
from retail.model import SYSTEM, Decision, ModelError

ORIGIN = "https://api.deepinfra.com/v1/openai"
DIMENSIONS = 1024


def config():
    return SimpleNamespace(
        deepinfra_api_key="unit-test-key",
        deepinfra_model="google/gemini-3.5-flash",
        deepinfra_embedding_model="Qwen/Qwen3-Embedding-8B",
    )


@pytest.fixture
def install(monkeypatch):
    real_client = httpx.Client

    def install_handler(handler):
        captured = {}

        def factory(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            kwargs = {**kwargs, "transport": httpx.MockTransport(handler)}
            return real_client(*args, **kwargs)

        monkeypatch.setattr(deepinfra.httpx, "Client", factory)
        return captured

    return install_handler


def decision_body(content, usage=None):
    body = {"choices": [{"message": {"content": content}}]}
    if usage is not None:
        body["usage"] = usage
    return body


def test_model_posts_bounded_schema_request_and_maps_usage(install):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=decision_body(
            json.dumps({"action": "answer", "text": "ok"}),
            usage={
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
                "completion_tokens_details": {"reasoning_tokens": 3},
            },
        ))

    captured = install(handler)
    decision, usage = deepinfra.DeepInfraModel(config()).decide(
        {"question": "revenue?", "tools": []}, remaining_seconds=100)

    assert decision == Decision(action="answer", text="ok")
    assert usage == {
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
        "thought_tokens": 3,
        "usage_source": "provider_measured",
        "cost": None,
    }
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == ORIGIN + "/chat/completions"
    assert request.headers["authorization"] == "Bearer unit-test-key"
    body = json.loads(request.content)
    assert body["model"] == "google/gemini-3.5-flash"
    assert body["temperature"] == 0
    assert body["max_tokens"] == 6000
    assert body["messages"][0] == {"role": "system", "content": SYSTEM}
    assert body["messages"][1]["role"] == "user"
    assert "revenue?" in body["messages"][1]["content"]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == deepinfra.decision_schema()
    assert captured["kwargs"]["timeout"] == 30.0


def test_model_parses_tool_call_for_openai_compatible_gateways(install):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "", "tool_calls": [{
                "type": "function", "function": {"name": "decision",
                    "arguments": json.dumps({"action": "answer", "text": "ok"})}
            }]}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        })

    captured = install(handler)
    cfg = SimpleNamespace(**vars(config()), deepinfra_use_tool_call=True)
    decision, usage = deepinfra.DeepInfraModel(cfg).decide({"question": "x"}, 10)

    assert decision == Decision(action="answer", text="ok")
    body = json.loads(requests[0].content)
    assert body["tool_choice"]["function"]["name"] == "decision"
    assert body["tools"][0]["function"]["name"] == "decision"
    assert "response_format" not in body
    assert captured["kwargs"]["timeout"] == 10.0


def test_openai_compatible_model_allows_bounded_longer_review_timeout(install):
    captured = install(lambda request: httpx.Response(200, json={
        "choices": [{"message": {"tool_calls": [{"function": {
            "arguments": json.dumps({"action": "answer", "text": "ok"})
        }}]}}]
    }))
    cfg = SimpleNamespace(**vars(config()), deepinfra_use_tool_call=True)
    deepinfra.DeepInfraModel(cfg).decide({"question": "x"}, 100)
    assert captured["kwargs"]["timeout"] == 60.0


def test_model_usage_defaults_to_none_without_provider_fields(install):
    install(lambda request: httpx.Response(200, json=decision_body(
        json.dumps({"action": "clarify", "text": "which period?"}))))
    _, usage = deepinfra.DeepInfraModel(config()).decide({"question": "x"}, 10)
    assert usage == {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "thought_tokens": None,
        "usage_source": "provider_measured",
        "cost": None,
    }


@pytest.mark.parametrize("remaining", [0, -5, float("nan"), float("inf"), None])
def test_model_refuses_expired_or_nonfinite_budget_without_request(install, remaining):
    def handler(request):
        raise AssertionError("Expired budget must not issue a request")

    install(handler)
    with pytest.raises(ModelError):
        deepinfra.DeepInfraModel(config()).decide({"question": "x"}, remaining)


@pytest.mark.parametrize("remaining,expected", [(100, 30.0), (5, 5.0), (0.25, 0.25)])
def test_model_timeout_is_bounded_by_budget_and_cap(install, remaining, expected):
    captured = install(lambda request: httpx.Response(200, json=decision_body(
        json.dumps({"action": "answer", "text": "ok"}))))
    deepinfra.DeepInfraModel(config()).decide({"question": "x"}, remaining)
    assert captured["kwargs"]["timeout"] == expected


@pytest.mark.parametrize("response", [
    httpx.Response(500, text="provider secret diagnostic"),
    httpx.Response(200, text="not-json provider secret"),
    httpx.Response(200, json={"choices": []}),
])
def test_model_sanitizes_http_and_payload_failures(install, response):
    install(lambda request: response)
    with pytest.raises(ModelError) as error:
        deepinfra.DeepInfraModel(config()).decide({"question": "x"}, 10)
    message = str(error.value).lower()
    assert "provider" not in message
    assert "secret" not in message


def test_model_sanitizes_transport_failure(install):
    def handler(request):
        raise httpx.ConnectError("network secret detail")

    install(handler)
    with pytest.raises(ModelError) as error:
        deepinfra.DeepInfraModel(config()).decide({"question": "x"}, 10)
    assert "secret" not in str(error.value).lower()


@pytest.mark.parametrize("content", [
    "not json",
    json.dumps({"action": "delete_everything"}),
    json.dumps({"action": "query", "sql": 123}),
    json.dumps([]),
])
def test_model_rejects_invalid_decisions(install, content):
    install(lambda request: httpx.Response(200, json=decision_body(content)))
    with pytest.raises(ModelError):
        deepinfra.DeepInfraModel(config()).decide({"question": "x"}, 10)


def embedding_response(vectors):
    return {"data": [{"index": index, "embedding": vector}
                     for index, vector in enumerate(vectors)]}


def test_embeddings_applies_query_instruction_only_to_queries(install):
    bodies, requests = [], []

    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        bodies.append(body)
        return httpx.Response(200, json=embedding_response(
            [[0.5] * DIMENSIONS for _ in body["input"]]))

    install(handler)
    embeddings = deepinfra.DeepInfraEmbeddings(config())
    embeddings.embed(["find boots"], "RETRIEVAL_QUERY", timeout=7)
    embeddings.embed(["a product document"], "RETRIEVAL_DOCUMENT", timeout=7)

    assert str(requests[0].url) == ORIGIN + "/embeddings"
    assert requests[0].headers["authorization"] == "Bearer unit-test-key"
    assert bodies[0]["input"][0].startswith("Instruct: Given a web search query")
    assert "\nQuery: find boots" in bodies[0]["input"][0]
    assert bodies[1]["input"] == ["a product document"]
    assert bodies[0]["model"] == "Qwen/Qwen3-Embedding-8B"
    assert bodies[0]["dimensions"] == DIMENSIONS
    assert "deepinfra" in embeddings.version
    assert "Qwen/Qwen3-Embedding-8B" in embeddings.version
    assert str(DIMENSIONS) in embeddings.version
    assert "instruction" in embeddings.version
    assert "instruct-v1" in embeddings.version


def test_embeddings_reorders_out_of_order_indices(install):
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"index": 2, "embedding": [3.0] * DIMENSIONS},
            {"index": 0, "embedding": [1.0] * DIMENSIONS},
            {"index": 1, "embedding": [2.0] * DIMENSIONS},
        ]})

    install(handler)
    vectors = deepinfra.DeepInfraEmbeddings(config()).embed(
        ["a", "b", "c"], "RETRIEVAL_DOCUMENT")
    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0]


@pytest.mark.parametrize("vector", [
    [0.1] * (DIMENSIONS - 1),
    [0.1] * (DIMENSIONS + 1),
    [float("nan")] + [0.1] * (DIMENSIONS - 1),
    [float("inf")] + [0.1] * (DIMENSIONS - 1),
    [True] + [0.1] * (DIMENSIONS - 1),
    ["x"] + [0.1] * (DIMENSIONS - 1),
    [],
])
def test_embeddings_rejects_malformed_vectors(install, vector):
    install(lambda request: httpx.Response(200, json={
        "data": [{"index": 0, "embedding": vector}]}))
    with pytest.raises(EmbeddingUnavailable):
        deepinfra.DeepInfraEmbeddings(config()).embed(["a"], "RETRIEVAL_DOCUMENT")


@pytest.mark.parametrize("data,texts", [
    ([], ["a"]),
    ([{"index": 0, "embedding": [0.1] * DIMENSIONS},
      {"index": 0, "embedding": [0.2] * DIMENSIONS}], ["a", "b"]),
    ([{"index": 0, "embedding": [0.1] * DIMENSIONS},
      {"index": 2, "embedding": [0.2] * DIMENSIONS}], ["a", "b"]),
    ([{"index": -1, "embedding": [0.1] * DIMENSIONS}], ["a"]),
    ([{"index": "0", "embedding": [0.1] * DIMENSIONS}], ["a"]),
    ([{"embedding": [0.1] * DIMENSIONS}], ["a"]),
    ([{"index": 0, "embedding": [0.1] * DIMENSIONS}], ["a", "b"]),
])
def test_embeddings_rejects_batch_index_cardinality_and_order(install, data, texts):
    install(lambda request: httpx.Response(200, json={"data": data}))
    with pytest.raises(EmbeddingUnavailable):
        deepinfra.DeepInfraEmbeddings(config()).embed(texts, "RETRIEVAL_DOCUMENT")


def test_embeddings_sanitizes_http_failure(install):
    install(lambda request: httpx.Response(500, text="provider secret diagnostic"))
    with pytest.raises(EmbeddingUnavailable) as error:
        deepinfra.DeepInfraEmbeddings(config()).embed(["a"], "RETRIEVAL_DOCUMENT")
    assert "secret" not in str(error.value).lower()
    assert "provider" not in str(error.value).lower()


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), None])
def test_embeddings_rejects_nonfinite_or_expired_timeout(install, timeout):
    def handler(request):
        raise AssertionError("Invalid timeout must not issue a request")

    install(handler)
    with pytest.raises(EmbeddingUnavailable):
        deepinfra.DeepInfraEmbeddings(config()).embed(
            ["a"], "RETRIEVAL_DOCUMENT", timeout=timeout)


def test_embeddings_empty_batch_makes_no_request(install):
    def handler(request):
        raise AssertionError("Empty batch must not issue a request")

    install(handler)
    assert deepinfra.DeepInfraEmbeddings(config()).embed([], "RETRIEVAL_DOCUMENT") == []
