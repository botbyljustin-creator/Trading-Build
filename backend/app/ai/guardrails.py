"""Post-hoc language guardrails for analyst agents (Module 15).

Prompt instructions alone are not a reliable control — this module adds a
deterministic second check. `strip_promissory_language` runs on every
string field of a `BacktestAnalysis`/`RobustnessAnalysis` before it is
persisted or returned to the frontend.
"""

from __future__ import annotations

import re

_BANNED_PATTERNS = [
    r"\bwill\s+make\s+money\b",
    r"\bguarantee(d|s)?\b",
    r"\bcan'?t\s+lose\b",
    r"\brisk[-\s]?free\b",
    r"\byou\s+should\s+trade\b",
    r"\byou\s+should\s+buy\b",
    r"\byou\s+should\s+sell\b",
    r"\bproven\s+to\s+work\b",
    r"\bsure\s+thing\b",
    r"\bwill\s+be\s+profitable\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _BANNED_PATTERNS]

_REDACTION_NOTICE = (
    "[removed: this system does not make profitability claims or trading " "recommendations]"
)


def sanitize_analyst_text(text: str) -> str:
    """Replace any banned promissory phrase with a neutral redaction notice.

    This is a defense-in-depth net, not the primary control — prompts also
    instruct the model not to produce this language. Sanitizing (rather
    than raising) keeps the rest of a genuinely useful observation intact.
    """
    sanitized = text
    for pattern in _COMPILED:
        sanitized = pattern.sub(_REDACTION_NOTICE, sanitized)
    return sanitized


def sanitize_string_list(items: list[str]) -> list[str]:
    return [sanitize_analyst_text(item) for item in items]
