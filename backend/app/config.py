from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:3000"
    database_url: str
    default_llm_provider: str = "ollama"
    cloud_provider: str = "openai"
    llm_timeout_seconds: float = 45.0
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    retrieval_top_k: int = 5
    retrieval_similarity_threshold: float = 0.35
    rag_temperature: float = 0.2
    rag_max_output_tokens: int = 1200
    ship30_max_output_tokens: int = 2400

    @field_validator("database_url", mode="before")
    @classmethod
    def use_async_postgres_driver(cls, value: str) -> str:
        """Render supplies postgres URLs without the asyncpg driver suffix."""
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return "postgresql+asyncpg://" + value[len("postgres://"):]
            if value.startswith("postgresql://"):
                return "postgresql+asyncpg://" + value[len("postgresql://"):]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
