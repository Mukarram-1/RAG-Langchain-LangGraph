"""Environment-driven application configuration."""

from functools import lru_cache
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from `.env` and process environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = "gpt-5"
    llm_temperature: float | None = None

    database_url: SecretStr = Field(default=SecretStr(""))
    db_pool_min_size: int = Field(default=1, ge=1)
    db_pool_max_size: int = Field(default=5, ge=1)
    db_command_timeout_seconds: float = Field(default=15.0, gt=0)
    db_statement_timeout_ms: int = Field(default=10_000, ge=100)

    sql_max_rows: int = Field(default=100, ge=1, le=1_000)
    sql_allowed_schemas: str = "public"

    @field_validator("db_pool_max_size")
    @classmethod
    def validate_pool_size(cls, value: int, info: object) -> int:
        """Keep the configured maximum at least as large as the minimum."""
        data = getattr(info, "data", {})
        minimum = data.get("db_pool_min_size", 1)
        if value < minimum:
            raise ValueError("DB_POOL_MAX_SIZE must be >= DB_POOL_MIN_SIZE")
        return value

    @property
    def allowed_schemas(self) -> tuple[str, ...]:
        return tuple(
            item.strip()
            for item in self.sql_allowed_schemas.split(",")
            if item.strip()
        )

    def require_database_url(self) -> str:
        value = self.database_url.get_secret_value()
        if not value:
            raise ValueError(
                "DATABASE_URL is required. Copy .env.example to .env and configure it."
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_chat_model(settings: Settings | None = None) -> BaseChatModel:
    """Build the selected provider without coupling agents to a vendor."""
    config = settings or get_settings()

    if config.llm_provider == "anthropic":
        api_key = config.anthropic_api_key.get_secret_value()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        options: dict[str, Any] = {
            "model": config.anthropic_model,
            "api_key": SecretStr(api_key),
            "max_retries": 2,
            "timeout": 60,
        }
        if config.llm_temperature is not None:
            options["temperature"] = config.llm_temperature
        return ChatAnthropic(**options)

    api_key = config.openai_api_key.get_secret_value()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for the OpenAI provider")
    options = {
        "model": config.openai_model,
        "api_key": SecretStr(api_key),
        "max_retries": 2,
        "timeout": 60,
    }
    if config.llm_temperature is not None:
        options["temperature"] = config.llm_temperature
    return ChatOpenAI(**options)
