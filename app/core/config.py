from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLMOps RAG Platform"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/llmops"
    max_upload_bytes: int = Field(default=10485760, gt=0, le=10485760)
    cors_origins: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]
    api_tokens: dict[str, SecretStr] = Field(default_factory=dict)
    admin_owners: list[str] = Field(default_factory=list)
    redact_sensitive_data: bool = False
    estimated_cost_per_million_tokens: float = Field(default=0, ge=0)
    rate_limit_per_minute: int = Field(default=30, ge=1)
    cache_ttl_seconds: int = Field(default=3600, ge=0)
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_max_chunks: int = Field(default=200, ge=1, le=500)
    ocr_enabled: bool = False
    ocr_languages: str = "por+eng"
    ocr_max_pages: int = Field(default=30, ge=1, le=100)
    ocr_timeout_seconds: int = Field(default=30, ge=1, le=120)
    worker_timeout_seconds: int = Field(default=600, ge=30, le=3600)
    multiagent_enabled: bool = True
    multiagent_model: str | None = Field(default=None, min_length=1)
    multiagent_max_steps: int = Field(default=3, ge=3, le=10)
    multiagent_timeout_seconds: float = Field(default=300, gt=0)

    chat_model: str = Field(
        default="qwen2.5:7b", validation_alias="OLLAMA_CHAT_MODEL", min_length=1
    )
    embedding_model_ollama: str = Field(
        default="nomic-embed-text", validation_alias="OLLAMA_EMBEDDING_MODEL", min_length=1
    )
    timeout: float = Field(default=300, validation_alias="OLLAMA_TIMEOUT_SECONDS", gt=0)
    default_temperature: float = Field(
        default=0.2, validation_alias="OLLAMA_TEMPERATURE", ge=0, le=2
    )
    default_max_tokens: int = Field(default=4096, validation_alias="OLLAMA_MAX_TOKENS", gt=0)
    base_url: str = Field(
        default="http://localhost:11434/v1",
        validation_alias="OLLAMA_BASE_URL",
        pattern=r"^https?://[^ ]+",
    )
    ollama_embedding_dimensions: int = Field(default=768, gt=0)
    ollama_max_context_chars: int = Field(default=24000, gt=0)

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
