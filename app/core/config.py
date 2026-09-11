from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLMOps RAG Platform"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/llmops"
    gemini_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("GEMINI_API_KEY")
    )
    gemini_model: str = Field(default="gemini-2.5-flash", pattern=r"^[a-zA-Z0-9._-]+$")
    gemini_timeout_seconds: float = Field(default=120, gt=0)
    max_upload_bytes: int = Field(default=10485760, gt=0, le=10485760)
    cors_origins: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]
    api_tokens: dict[str, SecretStr] = Field(default_factory=dict)
    rate_limit_per_minute: int = Field(default=30, ge=1)
    cache_ttl_seconds: int = Field(default=3600, ge=0)
    embedding_model: str = Field(default="gemini-embedding-001", pattern=r"^[a-zA-Z0-9._-]+$")
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_max_chunks: int = Field(default=200, ge=1, le=500)

    @field_validator("api_tokens")
    @classmethod
    def validate_tokens(cls, values):
        tokens = [token.get_secret_value() for token in values.values()]
        if len(set(tokens)) != len(tokens) or any(
            len(token) < 24 or token != token.strip() for token in tokens
        ):
            raise ValueError("Chave invalidaa")
        if any(not owner.strip() or len(owner) > 100 for owner in values):
            raise ValueError("Identificador invalido")
        return values

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )


settings = Settings()
