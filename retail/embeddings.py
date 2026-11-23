"""Small-corpus Gemini embeddings; persistent vectors live with versioned trios."""
class EmbeddingUnavailable(Exception):
    pass


class GeminiEmbeddings:
    def __init__(self, config):
        self.config = config
        self.version = config.embedding_model

    def embed(self, texts, task, timeout=10):
        from .model_privacy import sanitize_payload
        texts = sanitize_payload(texts, self.config.label_secret)
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=self.config.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(max(0.1, min(timeout, 15)) * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
                base_url=self.config.gemini_base_url))
        try:
            result = client.models.embed_content(model=self.version, contents=texts,
                config=types.EmbedContentConfig(task_type=task, output_dimensionality=768))
            vectors = [e.values for e in result.embeddings or []]
            if len(vectors) != len(texts) or any(not v for v in vectors):
                raise EmbeddingUnavailable()
            return vectors
        except Exception:
            raise EmbeddingUnavailable("Semantic retrieval unavailable; using lexical search.") from None
        finally:
            client.close()
