"""DeepInfra OpenAI-compatible adapters.

A fixed provider origin is used so no untrusted endpoint can be configured.
Every call has an explicit finite timeout, makes one attempt (no automatic
retries), validates the provider payload and raises sanitized errors that never
contain response bodies, request content or credentials.
"""
import json
import math

import httpx

from .embeddings import EmbeddingUnavailable
from .model import SYSTEM, Decision, ModelError

ORIGIN = "https://api.deepinfra.com/v1/openai"
BASE_URL = ORIGIN + "/"
CHAT_PATH = "chat/completions"
EMBEDDINGS_PATH = "embeddings"
DIMENSIONS = 1024
MAX_MODEL_TIMEOUT = 30.0
MAX_EMBEDDING_TIMEOUT = 15.0
MAX_TOKENS = 6000
QUERY_INSTRUCTION_VERSION = "instruct-v1"
QUERY_INSTRUCTION = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\n"
    "Query: "
)


def _finite_positive(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _token(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _model_timeout(remaining_seconds):
    if not _finite_positive(remaining_seconds):
        raise ModelError("Model unavailable or returned an invalid decision; no result was inferred.")
    return float(min(MAX_MODEL_TIMEOUT, remaining_seconds))


def _embedding_timeout(timeout):
    if not _finite_positive(timeout):
        raise EmbeddingUnavailable("Semantic retrieval unavailable; using lexical search.")
    return float(min(MAX_EMBEDDING_TIMEOUT, timeout))


def _headers(config):
    return {
        "Authorization": f"Bearer {config.deepinfra_api_key}",
        "Content-Type": "application/json",
    }


def decision_schema():
    # Conditional JSON Schema is accepted by this endpoint but not Google's
    # response_schema SDK type. Keep that provider constraint out of Decision.
    schema = Decision.model_json_schema()
    schema["allOf"] = [{"if": {"properties": {"action": {"const": "answer"}}},
                        "then": {"properties": {"text": {"minLength": 1}}}}]
    return schema


class DeepInfraModel:
    def __init__(self, config):
        self.config = config

    def decide(self, context, remaining_seconds):
        timeout = _model_timeout(remaining_seconds)
        payload = {
            "model": self.config.deepinfra_model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(context, default=str)},
            ],
            "temperature": 0,
            "max_tokens": MAX_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "decision",
                    "schema": decision_schema(),
                },
            },
        }
        try:
            with httpx.Client(base_url=getattr(self.config, "deepinfra_base_url", ORIGIN).rstrip("/") + "/", timeout=timeout, headers=_headers(self.config)) as client:
                response = client.post(CHAT_PATH, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if isinstance(content, dict):
                    decision = Decision.model_validate(content)
                elif isinstance(content, str):
                    decision = Decision.model_validate_json(content)
                else:
                    raise ValueError("unexpected decision content")
                usage = data.get("usage") or {}
                details = usage.get("completion_tokens_details") or {}
                return decision, {
                    "input_tokens": _token(usage.get("prompt_tokens")),
                    "output_tokens": _token(usage.get("completion_tokens")),
                    "total_tokens": _token(usage.get("total_tokens")),
                    "thought_tokens": _token(details.get("reasoning_tokens")),
                    "usage_source": "provider_measured",
                    "cost": None,
                }
        except Exception:
            raise ModelError(
                "Model unavailable or returned an invalid decision; no result was inferred."
            ) from None


class DeepInfraEmbeddings:
    def __init__(self, config):
        self.config = config
        self.version = (
            f"deepinfra:{config.deepinfra_embedding_model}:"
            f"dim={DIMENSIONS}:instruction={QUERY_INSTRUCTION_VERSION}"
        )

    def embed(self, texts, task, timeout=10):
        if not texts:
            return []
        timeout = _embedding_timeout(timeout)
        inputs = [
            QUERY_INSTRUCTION + text if task == "RETRIEVAL_QUERY" else text
            for text in texts
        ]
        payload = {
            "model": self.config.deepinfra_embedding_model,
            "input": inputs,
            "dimensions": DIMENSIONS,
        }
        try:
            with httpx.Client(base_url=getattr(self.config, "deepinfra_base_url", ORIGIN).rstrip("/") + "/", timeout=timeout, headers=_headers(self.config)) as client:
                response = client.post(EMBEDDINGS_PATH, json=payload)
                response.raise_for_status()
                data = response.json().get("data")
                if not isinstance(data, list) or len(data) != len(inputs):
                    raise ValueError("batch cardinality")
                indexed, seen = [], set()
                for item in data:
                    index = item.get("index")
                    if not isinstance(index, int) or isinstance(index, bool):
                        raise ValueError("index type")
                    if index < 0 or index >= len(inputs) or index in seen:
                        raise ValueError("index range or duplicate")
                    seen.add(index)
                    vector = item.get("embedding")
                    if not isinstance(vector, list) or len(vector) != DIMENSIONS:
                        raise ValueError("vector dimensions")
                    if not all(
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(value)
                        for value in vector
                    ):
                        raise ValueError("vector values")
                    indexed.append((index, [float(value) for value in vector]))
                if len(seen) != len(inputs):
                    raise ValueError("index coverage")
                indexed.sort(key=lambda pair: pair[0])
                return [vector for _, vector in indexed]
        except Exception:
            raise EmbeddingUnavailable("Semantic retrieval unavailable; using lexical search.") from None
