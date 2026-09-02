"""Pre-flight cost estimation (Module: Cost Controls).

Rough, intentionally conservative estimates used only to warn the user and
require confirmation before an expensive job runs — never used for actual
billing (real spend is tracked from provider usage after the fact).
"""

from __future__ import annotations

# USD per 1,000 input tokens. Deliberately approximate — kept in one place
# so it's easy to update as provider pricing changes.
_COST_PER_1K_INPUT_TOKENS_USD = {
    "anthropic": 0.003,
    "openai": 0.0025,
}

# Extraction reads each chunk more than once (concept pass + rule pass,
# plus contradiction/compile passes over already-extracted rules), so the
# effective token volume is a multiple of the raw transcript size.
_EFFECTIVE_TOKEN_MULTIPLIER = 2.5


def estimate_tokens_from_char_count(char_count: int) -> int:
    return max(1, char_count // 4)


def estimate_processing_cost_usd(
    total_transcript_tokens: int, provider: str = "anthropic"
) -> float:
    rate_per_1k = _COST_PER_1K_INPUT_TOKENS_USD.get(provider, 0.003)
    effective_tokens = total_transcript_tokens * _EFFECTIVE_TOKEN_MULTIPLIER
    return round(effective_tokens / 1000.0 * rate_per_1k, 4)
