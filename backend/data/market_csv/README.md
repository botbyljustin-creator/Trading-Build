# Market data directory

Put your backtest data here:

- `<SYMBOL>.csv` — columns `timestamp,open,high,low,close,volume`
- `<SYMBOL>.meta.json` — `{"timezone": "...", "asset_type": "...", "exchange_session": "..."}`

See `../../../BACKTESTING.md` for details. Files you add here are
gitignored (except this README) — they're local data, not part of the
repository.
