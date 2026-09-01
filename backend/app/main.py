"""FastAPI application entrypoint for US100 COMMAND.

Run locally with: `uvicorn app.main:app --reload` (see README.md for the
Docker Compose workflow, which is the primary supported way to run this).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "US100 COMMAND — AI-assisted NASDAQ-100 / US100 trading analysis "
            "platform. Deterministic signal, planning, and risk logic; AI "
            "provides advisory context only. No live-money execution in V1."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)

    @app.get("/", tags=["root"])
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    logger.info("app_created", app_env=settings.app_env)
    return app


app = create_app()
