"""Deterministic strategy compilation: Strategy Architect (`compiler.py`),
Strategy Auditor (`completeness.py`), and versioning diff (`versioning.py`).
No LLM calls happen anywhere in this package — a compiled
`StrategySpecification` must be exactly reproducible from its input rules.
"""
