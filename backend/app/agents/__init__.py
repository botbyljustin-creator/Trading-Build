"""LLM-backed and deterministic specialized agents (ARCHITECTURE.md §5).

LLM-backed: `knowledge_builder`, `rule_extractor`, `contradiction_analyst`,
`backtest_analyst`, `robustness_analyst`.
Deterministic (no LLM call): the Strategy Architect / Strategy Auditor /
Code Generator live in `app.strategy` and `app.codegen` respectively, since
they must never introduce model non-determinism into a compiled strategy.
"""
