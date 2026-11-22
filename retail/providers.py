"""Explicit service selection; provider errors never trigger service substitution."""
from .embeddings import GeminiEmbeddings
from .model import FixtureModel, GeminiModel


def model_for(config):
    if config.retail_mode == "fixture":
        return FixtureModel()
    if config.llm_provider in {"deepinfra", "openai_compatible"}:
        from .deepinfra import DeepInfraModel
        if config.llm_provider == "openai_compatible":
            config = config.model_copy(update={"deepinfra_api_key": config.openai_compatible_api_key, "deepinfra_base_url": config.openai_compatible_base_url, "deepinfra_model": config.openai_compatible_model, "deepinfra_use_tool_call": True})
        return DeepInfraModel(config)
    return GeminiModel(config)


def embeddings_for(config):
    if config.embedding_provider == "none":
        return None
    if config.embedding_provider == "deepinfra":
        from .deepinfra import DeepInfraEmbeddings
        return DeepInfraEmbeddings(config)
    return GeminiEmbeddings(config) if config.embedding_model else None
