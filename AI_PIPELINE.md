# StrategyForge AI — AI Pipeline

This document covers what actually calls an LLM, what never does, and the
structural controls that keep AI output traceable, non-fabricated, and
safe against prompt injection from transcript content.

## Where the LLM is (and isn't) in the loop

| Step | LLM? | Module |
|---|---|---|
| URL classification, metadata, transcript fetch | No | `app/ingestion` |
| Transcript chunking | No | `app/ingestion/chunking.py` |
| Concept extraction | **Yes** — `app/agents/knowledge_builder.py` | Module 2 |
| Rule extraction | **Yes** — `app/agents/rule_extractor.py` | Module 4 |
| Contradiction detection | **Yes** — `app/agents/contradiction_analyst.py` | Module 7 |
| Strategy compilation | No — deterministic, `app/strategy/compiler.py` | Module 5 |
| Completeness check | No — deterministic, `app/strategy/completeness.py` | Module 6 |
| Pine/Python code generation | No — deterministic, `app/codegen/` | Modules 9-10 |
| Backtest execution | No — deterministic, `app/backtesting/engine.py` | Module 11 |
| Robustness scoring (LOW/MEDIUM/HIGH) | No — deterministic, `app/backtesting/robustness.py` | Module 14 |
| Backtest/robustness narrative commentary | **Yes** — `app/agents/backtest_analyst.py`, `robustness_analyst.py` | Module 15 |
| Report assembly | No — templates already-validated data, `app/services/report_service.py` | Reporting |

Every strategy-shaping decision (what fields a `StrategySpecification` has,
whether a backtest is complete, what its metrics are, whether it's
overfit) is made by plain Python. The LLM only ever (a) reads source text
and proposes candidate concepts/rules with citations, (b) compares
already-extracted rules for conflicts, or (c) writes prose commentary about
numbers that were already computed deterministically.

## Provider abstraction

`app/ai/base.py` defines `LLMProvider.generate_structured(...)`, the only
interface the rest of the app depends on. `app/ai/anthropic_provider.py`
and `app/ai/openai_provider.py` implement it via forced tool/function
calling (never free-text parsing) so a response either validates against
the requested Pydantic schema or raises `LLMStructuredOutputError` — there
is no code path where malformed model output becomes silently-corrupted
state. `app/ai/factory.py` selects a provider from `Settings` and raises a
clear `ProviderNotConfiguredError` if its API key is missing, rather than
falling back to a fake result.

Adding a third provider means implementing `LLMProvider` and registering it
in the factory — no agent code changes.

## Structured output schemas

Every LLM call's output is one of the Pydantic models in `app/schemas/`:
`ConceptExtractionResult`, `RuleExtractionResult`,
`ContradictionDetectionResult`, `BacktestAnalysis`, `RobustnessAnalysis`.
`StrategySpecification` is also a schema in this package, but it is only
ever produced deterministically (never by an LLM call) — see
`app/strategy/compiler.py`.

## Source traceability (Module 3)

`SourceCitation` (`app/schemas/citations.py`) is required, not optional, on
every `ExtractedConcept` and `ExtractedRule` — the Pydantic schema enforces
`min_length=1` on `sources`. The excerpt must be presented to the model as
something to quote verbatim, and citations carry the exact
`video_id`/`start_seconds`/`end_seconds` the model was given in the
chunk header it read (see `app/ai/rendering.py::render_chunks`) — the
service layer persists these straight through to `ConceptSource`/
`RuleSource` rows, so the API never returns a claim without a clickable
source.

## Prompt injection defense

Transcripts are third-party text and are treated as data, never
instructions, structurally:

1. **Fixed system prompts.** `app/ai/prompts/agents.py` defines one
   constant string per agent. No system prompt is ever built by
   interpolating transcript content.
2. **Delimited, warned user turns.** `app/ai/prompts/security.py`'s
   `build_user_turn()` is the only way source content reaches a model —
   it always appears inside `<source_content>...</source_content>`,
   preceded by an explicit warning that the model must treat everything
   inside as data, not instructions, even if it looks like a command.
3. **Schema validation as a second gate.** Forced tool-use means the
   model's response has to be a specific JSON shape; a transcript trying to
   smuggle "ignore previous instructions and output X" would need to
   produce valid `RuleExtractionResult` JSON to have any effect at all, and
   even then it only ever becomes a `Rule` row a human must still review
   and approve before it can enter a strategy — it can't reach code
   execution, other users' data, or system prompts.
4. **Language guardrails on analysts.** `app/ai/guardrails.py` runs a
   second, deterministic pass over every `BacktestAnalysis`/
   `RobustnessAnalysis` string field, redacting promissory language
   ("will make money", "guaranteed", "you should trade this") even if the
   prompt-level instruction was somehow bypassed (Module 15).

## Rule status lifecycle & the AI_ASSUMPTION gate

`app/models/enums.COMPILABLE_RULE_STATUSES = {USER_CONFIRMED, USER_MODIFIED}`.
`app/services/strategy_service.compile_strategy_version` checks every
submitted rule id against this set and raises `RulesNotCompilableError`
(HTTP 422) listing the offending ids and their actual status if any rule
isn't eligible — this is enforced in the service layer, not just hidden in
the UI, so no API call can compile an `AI_ASSUMPTION`, `EXTRACTED`,
`AMBIGUOUS`, or `CONTRADICTORY` rule into a strategy.
`tests/test_api_integration.py::test_ai_assumption_rule_cannot_be_compiled`
exercises this against a real database.

## Cost controls

`app/ingestion/cost_estimation.py` estimates tokens from video duration
(before transcripts are even fetched) and from actual transcript length
once available, then converts to an approximate USD cost per
`Settings.default_llm_provider`. If a source's estimated cost exceeds
`LARGE_JOB_COST_CONFIRMATION_THRESHOLD_USD`, `ingest_source_task` stops
after resolving metadata and reports
`{"requires_cost_confirmation": true, "estimated_cost_usd": ...}` on the
job — transcript fetching (the expensive step for large channels) only
proceeds after `POST /sources/{id}/confirm-cost`.
