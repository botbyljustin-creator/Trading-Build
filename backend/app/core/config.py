"""Application configuration.

All configuration is loaded from environment variables (optionally via a
`.env` file in local development). Nothing here is hardcoded — see
`.env.example` at the repo root for the full list of variables.

Secrets (API keys, tokens, webhook secrets) are declared as `SecretStr` so
they are never accidentally rendered in logs, `repr()`, or FastAPI's
auto-generated docs.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings, sourced from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App identity -------------------------------------------------------
    app_name: str = "StrategyForge AI"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"

    # --- CORS -----------------------------------------------------------------
    cors_origins: str = "http://localhost:3000"

    # --- Database ---------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://strategyforge:strategyforge@localhost:5432/strategyforge",
        description="SQLAlchemy connection string for Postgres (pgvector extension required).",
    )

    # --- Redis / Celery -----------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="")
    celery_result_backend_url: str = Field(default="")

    # --- Security -------------------------------------------------------------
    secret_key: SecretStr = Field(default=SecretStr("changeme-dev-only-do-not-use-in-production"))

    # --- Clerk (authentication) ------------------------------------------------
    clerk_publishable_key: str = ""
    clerk_secret_key: SecretStr = Field(default=SecretStr(""))
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    # Development-only escape hatch: when true and no Clerk keys are set, a
    # single fixed dev user is used instead of verifying a Clerk token, so
    # the pipeline can be exercised locally without a Clerk account. Must be
    # false in any deployed environment.
    auth_dev_mode: bool = False

    # --- LLM providers -----------------------------------------------------
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = "gpt-4o"
    default_llm_provider: Literal["anthropic", "openai"] = "anthropic"

    # --- Cost controls -------------------------------------------------------
    # Hard ceiling on estimated USD cost for a single ingestion job before it
    # requires explicit user confirmation (Module: Cost Controls).
    large_job_cost_confirmation_threshold_usd: float = 2.0
    max_videos_per_channel_ingest: int = 500

    # --- Stripe (billing) ----------------------------------------------------
    stripe_secret_key: SecretStr = Field(default=SecretStr(""))
    stripe_webhook_secret: SecretStr = Field(default=SecretStr(""))
    stripe_publishable_key: str = ""

    # --- Market data ---------------------------------------------------------
    market_data_provider: Literal["csv"] = "csv"
    market_data_csv_dir: str = "./data/market_csv"

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_env(cls, value: str) -> str:
        return str(value).strip().lower()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def effective_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def effective_celery_result_backend_url(self) -> str:
        return self.celery_result_backend_url or self.redis_url


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
