"""Decoupled input type for the Strategy Compiler.

Keeping this separate from the `Rule` ORM model means `compiler.py` and
`completeness.py` can be unit-tested with plain Python objects, no database
required, and means the compiler cannot accidentally reach for ORM-only
fields (like `sources`) that don't matter to compilation.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import RuleCategory


class CompilableRule(BaseModel):
    id: str
    category: RuleCategory
    natural_language_rule: str
    machine_readable_rule: dict | None = None
    confidence: float = 1.0
