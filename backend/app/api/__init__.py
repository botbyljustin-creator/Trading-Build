"""FastAPI routers. Thin — delegates to app.services; owns request/response
schemas via app.schemas, never exposes ORM models directly.
"""
