"""Translates a rule's `machine_readable_rule` hint into parallel Pine and
Python boolean-expression snippets.

Only a small set of well-defined condition `type`s are actually rendered as
executable logic — this is a deliberately small, reviewable set, not an
attempt at general natural-language-to-code translation (which cannot be
done deterministically or safely). Anything else — the common case, since
most extracted rules are free text like "liquidity sweep below prior swing
low" — renders as an inert placeholder that always evaluates false and
carries a TODO comment quoting the exact rule text and its source rule
id(s). A generated strategy therefore never fabricates a trading condition
it cannot actually execute; it makes the gap visible instead.
"""

from __future__ import annotations

from dataclasses import dataclass

# The authoritative set of `machine_readable_rule.type` values that render
# as real logic. `app/backtesting/spec_evaluator.py` (which actually
# *executes* a spec against OHLCV data during a backtest, rather than just
# emitting source text) must recognize exactly this set —
# `tests/test_codegen_equivalence.py` asserts the two stay in lockstep so a
# type added to one is never silently missing from the other.
RECOGNIZED_CONDITION_TYPES = frozenset(
    {"price_above_ma", "price_below_ma", "vwap_reclaim", "vwap_rejection", "always_true"}
)


@dataclass(frozen=True)
class ConditionRender:
    pine: str
    python: str
    is_placeholder: bool


def _placeholder(natural_language_rule: str, rule_ids: list[str]) -> ConditionRender:
    citation = f"rule(s) {', '.join(rule_ids)}" if rule_ids else "no linked rule"
    safe_text = natural_language_rule.replace("*/", "* /").replace("\n", " ")
    pine = f"false // TODO not yet machine-translatable ({citation}): {safe_text}"
    python = f"False  # TODO not yet machine-translatable ({citation}): {safe_text!r}"
    return ConditionRender(pine=pine, python=python, is_placeholder=True)


def render_condition(
    natural_language_rule: str, machine_readable_rule: dict | None, rule_ids: list[str]
) -> ConditionRender:
    mrr = machine_readable_rule or {}
    condition_type = mrr.get("type")

    if condition_type == "price_above_ma":
        length = int(mrr.get("length", 200))
        ma = "ema" if str(mrr.get("ma_type", "EMA")).upper() == "EMA" else "sma"
        return ConditionRender(
            pine=f"close > ta.{ma}(close, {length})",
            python=f"close > {ma}(close, {length})",
            is_placeholder=False,
        )

    if condition_type == "price_below_ma":
        length = int(mrr.get("length", 200))
        ma = "ema" if str(mrr.get("ma_type", "EMA")).upper() == "EMA" else "sma"
        return ConditionRender(
            pine=f"close < ta.{ma}(close, {length})",
            python=f"close < {ma}(close, {length})",
            is_placeholder=False,
        )

    if condition_type == "vwap_reclaim":
        return ConditionRender(
            pine="close > vwapValue and close[1] <= vwapValue[1]",
            python="(close > vwap) & (close.shift(1) <= vwap.shift(1))",
            is_placeholder=False,
        )

    if condition_type == "vwap_rejection":
        return ConditionRender(
            pine="close < vwapValue and close[1] >= vwapValue[1]",
            python="(close < vwap) & (close.shift(1) >= vwap.shift(1))",
            is_placeholder=False,
        )

    if condition_type == "always_true":
        # Explicitly opted into by a user-provided rule, never by default.
        return ConditionRender(pine="true", python="True", is_placeholder=False)

    return _placeholder(natural_language_rule, rule_ids)
