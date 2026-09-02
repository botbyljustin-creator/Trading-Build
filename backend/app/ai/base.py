"""LLM provider abstraction.

Nothing above this layer (agents, services) ever imports `anthropic` or
`openai` directly — they depend only on `LLMProvider`, so switching or
adding a provider never touches agent code. Every call returns a validated
Pydantic model, never raw text, so a malformed response fails loudly
(`LLMStructuredOutputError`) instead of corrupting downstream state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base class for all LLM-provider errors."""


class LLMStructuredOutputError(LLMError):
    """The provider returned something that could not be validated against
    the requested Pydantic schema, even after the provider's own structured
    output enforcement (tool-use / json_schema mode)."""


class LLMProvider(ABC):
    """A chat-completion provider that can be asked to return a response
    conforming to a given Pydantic schema.

    Implementations must treat `source_content` as **untrusted data**: it is
    never concatenated into the system prompt, and the system prompt must
    always instruct the model that content in that block is data to analyze,
    not instructions to follow (see `app/ai/prompts/security.py`).
    """

    name: str

    @abstractmethod
    def generate_structured(
        self,
        *,
        system_prompt: str,
        source_content: str,
        instruction: str,
        response_model: type[T],
        max_tokens: int = 4096,
    ) -> T:
        """Return a `response_model` instance derived from `source_content`.

        `system_prompt` — fixed instructions for this agent (never contains
            interpolated source content).
        `source_content` — untrusted transcript/description text, passed as
            clearly delimited data.
        `instruction` — the specific ask for this call (e.g. "extract
            concepts from the following source_content").
        """
        raise NotImplementedError

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Rough token count for cost estimation (Module: Cost Controls).
        Does not need to be exact — used for pre-flight cost estimates."""
        raise NotImplementedError
