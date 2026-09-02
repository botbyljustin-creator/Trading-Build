"""FastAPI application entrypoint for StrategyForge AI.

Run locally with: `uvicorn app.main:app --reload` (see README.md for the
Docker Compose workflow, which is the primary supported way to run this).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.backtests import router as backtests_router
from app.api.routes.concepts import router as concepts_router
from app.api.routes.contradictions import router as contradictions_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.projects import router as projects_router
from app.api.routes.reports import router as reports_router
from app.api.routes.rules import router as rules_router
from app.api.routes.sources import router as sources_router
from app.api.routes.strategies import router as strategies_router
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
            "StrategyForge AI — turns educational trading content into "
            "structured, testable trading systems. Every extracted rule is "
            "traceable to its source; the AI never invents a rule to make a "
            "strategy 'complete.' No live-money execution in V1."
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
    app.include_router(projects_router)
    app.include_router(sources_router)
    app.include_router(concepts_router)
    app.include_router(rules_router)
    app.include_router(contradictions_router)
    app.include_router(strategies_router)
    app.include_router(backtests_router)
    app.include_router(jobs_router)
    app.include_router(reports_router)

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
