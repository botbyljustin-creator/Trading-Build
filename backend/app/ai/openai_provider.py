from __future__ import annotations

import json
from typing import TypeVar

import openai
from pydantic import BaseModel, ValidationError

from app.ai.base import LLMProvider, LLMStructuredOutputError
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_TOOL_NAME = "emit_structured_result"


class OpenAIProvider(LLMProvider):
    """Structured output via forced function-calling, mirroring
    `AnthropicProvider` so both providers behave identically from the
    agent's point of view."""

    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = openai.OpenAI(api_key=api_key)
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
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_turn},
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": _TOOL_NAME,
                            "description": f"Emit the result as {response_model.__name__}.",
                            "parameters": schema,
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            )
        except openai.APIError as exc:
            raise LLMStructuredOutputError(f"OpenAI API error: {exc}") from exc

        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        for call in tool_calls:
            if call.function.name == _TOOL_NAME:
                try:
                    parsed = json.loads(call.function.arguments)
                    return response_model.model_validate(parsed)
                except (json.JSONDecodeError, ValidationError) as exc:
                    logger.warning("openai_structured_output_invalid", error=str(exc))
                    raise LLMStructuredOutputError(
                        f"Response did not match {response_model.__name__}: {exc}"
                    ) from exc

        raise LLMStructuredOutputError("OpenAI response contained no matching tool call.")

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
