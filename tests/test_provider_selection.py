"""Provider selection must never silently substitute one live service for another."""
import json
import pytest

from retail.config import Settings


def config(**overrides):
    return Settings(_env_file=None, **overrides)


def test_deepinfra_live_config_does_not_require_a_google_model_key():
    settings = config(retail_mode="live", llm_provider="deepinfra",
        embedding_provider="deepinfra", deepinfra_api_key="unit-key",
        google_cloud_project="unit-project", label_secret="unit-secret",
        api_tokens_json='{"unit-token":"alice"}')
    settings.validate_live()


def test_deepinfra_live_config_requires_its_own_key():
    settings = config(retail_mode="live", llm_provider="deepinfra",
        embedding_provider="deepinfra", gemini_api_key="google-key", gemini_model="google-model",
        google_cloud_project="unit-project", label_secret="unit-secret",
        api_tokens_json='{"unit-token":"alice"}')
    with pytest.raises(ValueError, match="DeepInfra"):
        settings.validate_live()


def test_provider_factories_preserve_fixture_and_google_paths():
    from retail.providers import model_for, embeddings_for
    from retail.model import FixtureModel, GeminiModel
    from retail.embeddings import GeminiEmbeddings
    from retail.deepinfra import DeepInfraModel, DeepInfraEmbeddings

    assert isinstance(model_for(config(llm_provider="deepinfra")), FixtureModel)
    assert isinstance(model_for(config(retail_mode="live")), GeminiModel)
    assert isinstance(embeddings_for(config()), GeminiEmbeddings)
    assert embeddings_for(config(embedding_provider="none")) is None
    deep = config(retail_mode="live", llm_provider="deepinfra", embedding_provider="deepinfra")
    assert isinstance(model_for(deep), DeepInfraModel)
    assert isinstance(embeddings_for(deep), DeepInfraEmbeddings)


def test_embedding_provider_has_independent_live_credentials():
    settings = config(retail_mode="live", llm_provider="deepinfra", embedding_provider="gemini",
        deepinfra_api_key="unit-key", google_cloud_project="unit-project",
        label_secret="unit-secret", api_tokens_json='{"unit-token":"alice"}')
    with pytest.raises(ValueError, match="embedding"):
        settings.validate_live()


def test_agent_uses_deepinfra_and_records_actual_model_in_trace(tmp_path, monkeypatch):
    import httpx
    from retail.agent import Agent
    from retail.store import Store
    from retail.security import principal_for
    import retail.deepinfra as adapter

    real_client = httpx.Client
    def response(request):
        assert json.loads(request.content)["model"] == "google/gemini-3.7-flash"
        return httpx.Response(200, json={"choices": [{"message": {"content":
            '{"action":"clarify","text":"Which period should I compare?"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
    monkeypatch.setattr(adapter.httpx, "Client", lambda **kwargs:
        real_client(**kwargs, transport=httpx.MockTransport(response)))
    settings = config(retail_mode="live", llm_provider="deepinfra", embedding_provider="none",
        deepinfra_api_key="unit-key", log_path=str(tmp_path / "events.jsonl"))
    store = Store(f"sqlite:///{tmp_path}/state.db")
    events = []
    try:
        result = Agent(settings, store).chat(principal_for("alice", settings), "Compare revenue", sink=events.append)
        assert result["answer"] == "Which period should I compare?"
        usage = next(e for e in events if e["stage"] == "model_usage")
        assert usage["model"] == "google/gemini-3.7-flash"
        assert usage["provider"] == "deepinfra"
        assert usage["input_tokens"] == 10
    finally:
        store.engine.dispose()

def test_openai_compatible_gateway_has_its_own_credentials_and_model():
    settings = config(retail_mode="live", llm_provider="openai_compatible", embedding_provider="none",
        openai_compatible_api_key="unit-key", openai_compatible_base_url="https://gateway.example/v1",
        openai_compatible_model="gemini-4-neon", google_cloud_project="unit-project",
        label_secret="unit-secret", api_tokens_json='{"unit-token":"alice"}')
    settings.validate_live()
    from retail.providers import model_for
    from retail.deepinfra import DeepInfraModel
    assert isinstance(model_for(settings), DeepInfraModel)
