"""Explicit service selection; provider errors never trigger service substitution."""
from .embeddings import GeminiEmbeddings
from .model import FixtureModel, GeminiModel


def model_for(config):
    if config.retail_mode == "fixture":
        return FixtureModel()
    if config.llm_provider == "deepinfra":
        from .deepinfra import DeepInfraModel
        return DeepInfraModel(config)
    return GeminiModel(config)


def embeddings_for(config):
    if config.embedding_provider == "none":
        return None
    if config.embedding_provider == "deepinfra":
        from .deepinfra import DeepInfraEmbeddings
        return DeepInfraEmbeddings(config)
    return GeminiEmbeddings(config) if config.embedding_model else None
