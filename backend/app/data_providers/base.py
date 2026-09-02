"""`MarketDataProvider` interface (Module: Data Provider Abstraction).

The backtest engine and every route that accepts a data source depend only
on this interface, never on a specific vendor, and every implementation
must return bars carrying an explicit, tz-aware UTC index — "the market"
is never assumed; a caller always names a concrete `provider` + `symbol`
(see ARCHITECTURE.md §8 on why US100/NAS100/... are not interchangeable).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class SymbolInfo:
    provider: str
    symbol: str
    timezone: str
    asset_type: str
    exchange_session: str | None = None


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def get_historical_bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Return OHLCV bars with a tz-aware UTC `DatetimeIndex` and columns
        `open`, `high`, `low`, `close`, `volume`, sorted ascending, with no
        gaps silently filled (missing bars stay missing — see
        ARCHITECTURE.md's fail-closed rule on stale/malformed data)."""
        raise NotImplementedError

    @abstractmethod
    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        raise NotImplementedError

    @abstractmethod
    def get_trading_calendar(self, symbol: str) -> list[str] | None:
        """Return known non-trading dates (ISO date strings), or None if the
        provider doesn't track one — the caller must not assume every
        weekday is a trading day when this is unavailable."""
        raise NotImplementedError
