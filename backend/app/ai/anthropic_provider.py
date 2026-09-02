from __future__ import annotations

from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.ai.base import LLMProvider, LLMStructuredOutputError
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_TOOL_NAME = "emit_structured_result"


class AnthropicProvider(LLMProvider):
    """Structured output via forced tool-use: the schema is registered as a
    single tool and `tool_choice` forces the model to call it, so the
    response body is (schema-conformant) JSON rather than free prose.
    """

    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate_structured(
        self,
        *,
        system_prompt: str,
        source_content: str,
        instruction: str,
        response_model: type[T],
        max_tokens: int = 4096,
    ) -> T:
        from app.ai.prompts.security import build_user_turn

        user_turn = build_user_turn(instruction=instruction, source_content=source_content)
        schema = response_model.model_json_schema()

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                tools=[
                    {
                        "name": _TOOL_NAME,
                        "description": f"Emit the result as {response_model.__name__}.",
                        "input_schema": schema,
                    }
                ],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": user_turn}],
            )
        except anthropic.APIError as exc:
            raise LLMStructuredOutputError(f"Anthropic API error: {exc}") from exc

        for block in response.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                try:
                    return response_model.model_validate(block.input)
                except ValidationError as exc:
                    logger.warning("anthropic_structured_output_invalid", error=str(exc))
                    raise LLMStructuredOutputError(
                        f"Response did not match {response_model.__name__}: {exc}"
                    ) from exc

        raise LLMStructuredOutputError("Anthropic response contained no tool_use block.")

    def estimate_tokens(self, text: str) -> int:
        # Conservative heuristic (~4 chars/token for English text). Exact
        # counts require a live API call; this is only used for pre-flight
        # cost estimates, not billing.
        return max(1, len(text) // 4)
