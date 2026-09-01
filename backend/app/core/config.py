"""Application configuration.

All configuration is loaded from environment variables (optionally via a
`.env` file in local development). Nothing here is hardcoded — see
`.env.example` at the repo root for the full list of variables the system
will eventually use across every phase.

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

    # --- App identity -----------------------------------------------------
    app_name: str = "US100 COMMAND"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"

    # --- CORS ---------------------------------------------------------------
    cors_origins: str = "http://localhost:3000"

    # --- Database -----------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://us100:us100@localhost:5432/us100_command",
        description="SQLAlchemy connection string for Postgres.",
    )

    # --- Redis --------------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Security -------------------------------------------------------------
    secret_key: SecretStr = Field(
        default=SecretStr("changeme-dev-only-do-not-use-in-production"),
    )

    # --- TradingView webhook (Phase 2) --------------------------------------
    tradingview_webhook_secret: SecretStr = Field(default=SecretStr(""))

    # --- Anthropic Claude (Phase 8) ------------------------------------------
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_model: str = "claude-sonnet-5"

    # --- Telegram (Phase 7) --------------------------------------------------
    telegram_bot_token: SecretStr = Field(default=SecretStr(""))
    telegram_chat_id: str = ""

    # --- Email notifications (interface only in V1) --------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = Field(default=SecretStr(""))
    email_from_address: str = ""

    # --- Live trading safety gate (inert in V1, see docs/LIVE_TRADING_FUTURE.md) --
    live_trading_enabled: bool = False

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


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
