from __future__ import annotations

from functools import lru_cache
from typing import Literal

from app.ai.base import LLMProvider
from app.core.config import get_settings

ProviderName = Literal["anthropic", "openai"]


class ProviderNotConfiguredError(RuntimeError):
    """Raised when the requested provider has no API key configured."""


@lru_cache
def get_llm_provider(provider: ProviderName | None = None) -> LLMProvider:
    """Return the configured `LLMProvider`. Defaults to
    `Settings.default_llm_provider`. Cached per-process per-provider-name —
    providers are stateless aside from their client, so this is safe."""
    settings = get_settings()
    resolved = provider or settings.default_llm_provider

    if resolved == "anthropic":
        api_key = settings.anthropic_api_key.get_secret_value()
        if not api_key:
            raise ProviderNotConfiguredError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env to use the Anthropic provider."
            )
        from app.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=api_key, model=settings.anthropic_model)

    if resolved == "openai":
        api_key = settings.openai_api_key.get_secret_value()
        if not api_key:
            raise ProviderNotConfiguredError(
                "OPENAI_API_KEY is not set. Add it to your .env to use the OpenAI provider."
            )
        from app.ai.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=api_key, model=settings.openai_model)

    raise ValueError(f"Unknown LLM provider: {resolved}")
