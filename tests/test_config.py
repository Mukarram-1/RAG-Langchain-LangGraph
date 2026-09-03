"""Provider configuration tests without network calls."""

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from src.config import Settings, get_chat_model


def test_builds_anthropic_model_from_config() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="anthropic",
        anthropic_api_key="test-key",
    )

    model = get_chat_model(settings)

    assert isinstance(model, ChatAnthropic)
    assert model.model == "claude-sonnet-5"


def test_builds_openai_model_from_config() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="openai",
        openai_api_key="test-key",
    )

    model = get_chat_model(settings)

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-5"
