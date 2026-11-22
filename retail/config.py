from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./retail.db"
    # Fixture is explicit and never reported as live integration.
    retail_mode: str = "fixture"
    api_tokens_json: str = '{"alice-local-token":"alice","bob-local-token":"bob"}'
    entitlements_json: str = '{"alice":[1,2],"bob":[3]}'
    brand_access_json: str = ""
    minimum_cohort_size: int = Field(default=5, ge=2, le=10000)
    churn_window_days: int = Field(default=90, ge=1, le=3650)
    adapter_secret: str = ""
    webui_users_json: str = "{}"
    gemini_api_key: str = ""
    gemini_model: str = ""
    llm_provider: Literal["gemini", "deepinfra"] = "gemini"
    embedding_provider: Literal["gemini", "deepinfra", "none"] = "gemini"
    deepinfra_api_key: str = ""
    deepinfra_base_url: str = "https://api.deepinfra.com/v1/openai"
    deepinfra_model: str = "google/gemini-3.7-flash"
    deepinfra_review_model: str = ""
    deepinfra_embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    embedding_model: str = "gemini-embedding-001"
    retrieval_min_similarity: float = 0.65
    retrieval_lexical_min_similarity: float = Field(default=0.60, ge=0, le=1)
    google_cloud_project: str = ""
    label_secret: str = "local-fixture-label-secret"
    maximum_bytes_billed: int = Field(default=100_000_000, ge=1, le=1_000_000_000)
    max_queries: int = Field(default=4, ge=1, le=10)
    max_model_calls: int = Field(default=7, ge=1, le=20)
    max_seconds: int = Field(default=90, ge=1, le=300)
    max_rows: int = Field(default=100, ge=1, le=1000)
    max_result_bytes: int = Field(default=64000, ge=1024, le=1000000)
    max_context_chars: int = Field(default=80000, ge=2000, le=250000)
    log_path: str = "./events.jsonl"
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "http://localhost:3001"

    def validate_live(self):
        if self.retail_mode not in {"fixture", "live"}:
            raise ValueError("RETAIL_MODE must be fixture or live")
        if self.retail_mode == "live":
            if not self.google_cloud_project:
                raise ValueError("Live mode requires a GCP execution project")
            if self.llm_provider == "gemini" and not all([self.gemini_api_key, self.gemini_model]):
                raise ValueError("Google Gemini requires GEMINI_API_KEY and GEMINI_MODEL")
            if self.llm_provider == "deepinfra" and not all([self.deepinfra_api_key, self.deepinfra_model]):
                raise ValueError("DeepInfra requires DEEPINFRA_API_KEY and DEEPINFRA_MODEL")
            self.validate_embeddings()
            if self.label_secret == "local-fixture-label-secret":
                raise ValueError("Live mode requires a dedicated LABEL_SECRET")
            if "local-token" in self.api_tokens_json:
                raise ValueError("Replace demo API tokens before using live mode")

    def validate_embeddings(self):
        if self.embedding_provider == "gemini" and self.embedding_model and not self.gemini_api_key:
            raise ValueError("Google embedding requires GEMINI_API_KEY")
        if self.embedding_provider == "deepinfra" and not all([self.deepinfra_api_key, self.deepinfra_embedding_model]):
            raise ValueError("DeepInfra embedding requires DEEPINFRA_API_KEY and DEEPINFRA_EMBEDDING_MODEL")


@lru_cache
def settings():
    result = Settings()
    result.validate_live()
    return result
