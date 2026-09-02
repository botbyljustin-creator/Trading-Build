"""Pydantic DTOs shared across the ingestion/AI/strategy/backtesting
pipeline. API request/response models specific to one route live alongside
that route in `app/api/routes/`; the schemas here are the cross-cutting
contracts multiple modules (and the LLM structured-output layer) share."""
