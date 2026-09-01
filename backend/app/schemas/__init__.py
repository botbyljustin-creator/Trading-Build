"""Pydantic request/response/DTO schemas for the API layer.

ORM models (`app.models`) are never returned directly from API endpoints —
every response shape is defined explicitly here so the wire contract is
stable and intentional. Empty in Phase 1 beyond what `health.py` needs
inline; grows alongside `app.api.routes` in later phases.
"""
