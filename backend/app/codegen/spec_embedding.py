"""Embeds the exact `StrategySpecification` JSON that a generated file was
rendered from, as a comment block, in both Pine and Python output.

This is what Module 10's "Pine and Python share the same underlying spec so
logic does not silently diverge" is verified against
(`tests/test_codegen_equivalence.py`): both generators are handed the same
`StrategySpecification` instance and both embed it verbatim, so a test can
extract and compare the two blocks without needing a Pine Script
interpreter.
"""

from __future__ import annotations

import json

from app.schemas.strategy_spec import StrategySpecification

_BEGIN = "STRATEGYFORGE_SPEC_JSON_BEGIN"
_END = "STRATEGYFORGE_SPEC_JSON_END"


def embed_spec_comment(spec: StrategySpecification, comment_prefix: str) -> str:
    payload = json.dumps(spec.model_dump(mode="json"), indent=2, sort_keys=True)
    lines = [f"{comment_prefix} {_BEGIN}"]
    lines += [f"{comment_prefix} {line}" for line in payload.splitlines()]
    lines.append(f"{comment_prefix} {_END}")
    return "\n".join(lines)


def extract_spec_json(code: str, comment_prefix: str) -> dict:
    lines = code.splitlines()
    begin_marker = f"{comment_prefix} {_BEGIN}"
    end_marker = f"{comment_prefix} {_END}"
    try:
        start = lines.index(begin_marker) + 1
        end = lines.index(end_marker)
    except ValueError as exc:
        raise ValueError("Spec JSON embedding markers not found in generated code.") from exc
    payload_lines = [line[len(comment_prefix) + 1 :] for line in lines[start:end]]
    return json.loads("\n".join(payload_lines))
