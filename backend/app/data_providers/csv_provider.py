"""CSV `MarketDataProvider` — the only implementation V1 ships with.

Reads `{base_dir}/{symbol}.csv` with columns `timestamp,open,high,low,close,volume`
(timestamp ISO-8601, any offset — converted to UTC on load) and an optional
sidecar `{base_dir}/{symbol}.meta.json` with `{"timezone": "...",
"asset_type": "...", "exchange_session": "..."}`. If the sidecar is
missing, `get_symbol_info` raises rather than guessing a timezone/asset
type for an instrument as ambiguous as "US100" (ARCHITECTURE.md §8).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.data_providers.base import MarketDataProvider, SymbolInfo

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


class SymbolDataNotFoundError(FileNotFoundError):
    pass


class SymbolMetadataMissingError(FileNotFoundError):
    pass


class CSVMarketDataProvider(MarketDataProvider):
    name = "csv"

    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir)

    def _csv_path(self, symbol: str) -> Path:
        return self._base_dir / f"{symbol}.csv"

    def _meta_path(self, symbol: str) -> Path:
        return self._base_dir / f"{symbol}.meta.json"

    def get_historical_bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> pd.DataFrame:
        path = self._csv_path(symbol)
        if not path.exists():
            raise SymbolDataNotFoundError(
                f"No CSV found for symbol '{symbol}' at {path}. "
                "Upload a CSV named '<symbol>.csv' with columns "
                "timestamp,open,high,low,close,volume."
            )
        df = pd.read_csv(path)
        missing = [c for c in ["timestamp", *REQUIRED_COLUMNS] if c not in df.columns]
        if missing:
            raise ValueError(f"CSV for '{symbol}' is missing required columns: {missing}")

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="first")]

        if not df.index.is_monotonic_increasing:
            raise ValueError(
                f"CSV for '{symbol}' has out-of-order timestamps after sort — data issue."
            )

        start_utc = (
            pd.Timestamp(start).tz_convert("UTC")
            if pd.Timestamp(start).tzinfo
            else pd.Timestamp(start, tz="UTC")
        )
        end_utc = (
            pd.Timestamp(end).tz_convert("UTC")
            if pd.Timestamp(end).tzinfo
            else pd.Timestamp(end, tz="UTC")
        )
        windowed = df.loc[(df.index >= start_utc) & (df.index <= end_utc), REQUIRED_COLUMNS]
        return windowed

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        meta_path = self._meta_path(symbol)
        if not meta_path.exists():
            raise SymbolMetadataMissingError(
                f"No metadata sidecar found for '{symbol}' at {meta_path}. "
                "StrategyForge AI never assumes a timezone/asset type for an "
                "instrument like this — create '<symbol>.meta.json' with "
                '{"timezone": "...", "asset_type": "...", "exchange_session": "..."}.'
            )
        meta = json.loads(meta_path.read_text())
        return SymbolInfo(
            provider=self.name,
            symbol=symbol,
            timezone=meta["timezone"],
            asset_type=meta["asset_type"],
            exchange_session=meta.get("exchange_session"),
        )

    def get_trading_calendar(self, symbol: str) -> list[str] | None:
        # Not tracked by the CSV provider — callers must not assume every
        # weekday without a gap in the data is a trading day.
        return None
