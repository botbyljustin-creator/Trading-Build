"""Deterministic instrument tagging (Module 12/19: distinguish instruments,
filter by market). Pure keyword/regex matching — never an LLM call — so
filtering by instrument never depends on an API key being configured and
never varies between runs on identical text.

Deliberately conservative: a tag is only added on a fairly specific match
(word-boundary, common tickers/abbreviations) to avoid tagging every rule
that happens to mention "the market" as NASDAQ-relevant.
"""

from __future__ import annotations

import re

_PATTERNS: dict[str, re.Pattern[str]] = {
    "NQ": re.compile(r"\bnq\b|e-?mini nasdaq|/nq\b", re.IGNORECASE),
    "NASDAQ_100": re.compile(r"nasdaq-?100|\bndx\b|nasdaq composite", re.IGNORECASE),
    "US100": re.compile(r"\bus100\b|\bus[\s-]100\b", re.IGNORECASE),
    "NAS100": re.compile(r"\bnas100\b", re.IGNORECASE),
    "SP500": re.compile(r"\bspx\b|s&p ?500|\bes\b futures|e-?mini s&?p", re.IGNORECASE),
    "DOW": re.compile(r"\bdow\b|\bymm?\b|us30", re.IGNORECASE),
    "DXY": re.compile(r"\bdxy\b|dollar index", re.IGNORECASE),
    "GOLD": re.compile(r"\bgold\b|\bxau ?usd\b", re.IGNORECASE),
    "FOREX": re.compile(r"\beur ?usd\b|\bgbp ?usd\b|\busd ?jpy\b|\bforex\b", re.IGNORECASE),
    "CRUDE_OIL": re.compile(r"\bcrude\b|\bwti\b|\bcl\b futures", re.IGNORECASE),
}


def tag_instruments(*texts: str) -> list[str]:
    """Returns the sorted list of instrument tags matched anywhere in
    `texts`. Multiple tags can apply (e.g. a rule mentioning both NQ and
    DXY correlation)."""
    haystack = " ".join(t for t in texts if t)
    return sorted(tag for tag, pattern in _PATTERNS.items() if pattern.search(haystack))
