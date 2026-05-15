"""Read-only Alpaca REST client for the trading-desk dashboards.

Wraps the trading API (account / clock / positions / portfolio history /
activities) and the market-data API (bars, for the SPY benchmark). The
dashboard NEVER places orders — this client has no write methods.

A single dashboard render touches /account, /clock, /positions etc. once
each, so the client memoizes GETs for a short TTL to avoid hammering the
same endpoint when several panels need the same data.

Free / paper Alpaca accounts only get the IEX market-data feed (15-min
delayed); that's fine for a dashboard. Bars therefore request feed=iex.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

TRADING_PAPER = "https://paper-api.alpaca.markets"
TRADING_LIVE = "https://api.alpaca.markets"
DATA_BASE = "https://data.alpaca.markets"


class AlpacaError(RuntimeError):
    def __init__(self, status: int, body: str, endpoint: str):
        super().__init__(f"Alpaca {endpoint} -> HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body
        self.endpoint = endpoint


class AlpacaClient:
    def __init__(
        self,
        key: str,
        secret: str,
        paper: bool = True,
        cache_ttl: float = 5.0,
        timeout: float = 12.0,
    ):
        if not key or not secret:
            raise ValueError("Alpaca key/secret required")
        self.paper = paper
        self.trading_base = TRADING_PAPER if paper else TRADING_LIVE
        self.data_base = DATA_BASE
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "APCA-API-KEY-ID": key,
                "APCA-API-SECRET-KEY": secret,
                "accept": "application/json",
            },
        )

    # ── internals ──────────────────────────────────────────────────
    def _get(
        self,
        base: str,
        path: str,
        params: Optional[dict] = None,
        *,
        cache: bool = True,
    ) -> Any:
        ckey = f"{base}{path}?{sorted((params or {}).items())}"
        if cache and ckey in self._cache:
            ts, val = self._cache[ckey]
            if time.time() - ts < self._cache_ttl:
                return val
        resp = self._client.get(base + path, params=params)
        if resp.status_code != 200:
            raise AlpacaError(resp.status_code, resp.text, path)
        data = resp.json()
        if cache:
            self._cache[ckey] = (time.time(), data)
        return data

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AlpacaClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ── trading API ────────────────────────────────────────────────
    def get_clock(self) -> dict:
        """{timestamp, is_open, next_open, next_close}"""
        return self._get(self.trading_base, "/v2/clock")

    def get_account(self) -> dict:
        return self._get(self.trading_base, "/v2/account")

    def get_positions(self) -> list[dict]:
        return self._get(self.trading_base, "/v2/positions")

    def get_portfolio_history(
        self,
        period: str = "1A",
        timeframe: str = "1D",
        extended_hours: bool = False,
    ) -> dict:
        """{timestamp[], equity[], profit_loss[], profit_loss_pct[],
        base_value, timeframe}"""
        return self._get(
            self.trading_base,
            "/v2/account/portfolio/history",
            {
                "period": period,
                "timeframe": timeframe,
                "extended_hours": str(extended_hours).lower(),
            },
        )

    def get_activities(
        self,
        activity_types: Optional[str] = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Account activities (FILL, DIV, ...). Not cached — feed needs
        freshest data. activity_types is a comma list, e.g. 'FILL'."""
        params: dict = {"page_size": page_size}
        if activity_types:
            params["activity_types"] = activity_types
        return self._get(
            self.trading_base, "/v2/account/activities", params, cache=False
        )

    # ── market data API ────────────────────────────────────────────
    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Daily bars for one symbol. Used for the SPY benchmark line.
        start/end are RFC-3339 / YYYY-MM-DD strings."""
        params: dict = {
            "symbols": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "adjustment": "all",
            "feed": "iex",
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        data = self._get(self.data_base, "/v2/stocks/bars", params)
        return data.get("bars", {}).get(symbol, [])

    # ── normalized convenience views ───────────────────────────────
    def account_snapshot(self) -> dict:
        """Flat, typed view the dashboard hero KPIs consume directly."""
        a = self.get_account()
        equity = float(a.get("equity", 0) or 0)
        last_equity = float(a.get("last_equity", 0) or 0)
        day_pl = equity - last_equity
        day_pl_pct = (day_pl / last_equity * 100) if last_equity else 0.0
        return {
            "account_number": a.get("account_number"),
            "status": a.get("status"),
            "currency": a.get("currency", "USD"),
            "equity": equity,
            "last_equity": last_equity,
            "cash": float(a.get("cash", 0) or 0),
            "buying_power": float(a.get("buying_power", 0) or 0),
            "portfolio_value": float(a.get("portfolio_value", equity) or equity),
            "day_pl": day_pl,
            "day_pl_pct": day_pl_pct,
            "pattern_day_trader": bool(a.get("pattern_day_trader", False)),
            "daytrade_count": int(a.get("daytrade_count", 0) or 0),
            "is_paper": self.paper,
        }

    def positions_normalized(self) -> list[dict]:
        """Positions with numeric fields parsed (Alpaca returns strings)."""
        out = []
        for p in self.get_positions():
            qty = float(p.get("qty", 0) or 0)
            avg = float(p.get("avg_entry_price", 0) or 0)
            mv = float(p.get("market_value", 0) or 0)
            upl = float(p.get("unrealized_pl", 0) or 0)
            uplpc = float(p.get("unrealized_plpc", 0) or 0) * 100
            cur = float(p.get("current_price", 0) or 0)
            out.append(
                {
                    "symbol": p.get("symbol"),
                    "qty": qty,
                    "avg_entry_price": avg,
                    "current_price": cur,
                    "market_value": mv,
                    "unrealized_pl": upl,
                    "unrealized_pl_pct": uplpc,
                    "side": p.get("side", "long"),
                    "asset_class": p.get("asset_class", "us_equity"),
                }
            )
        return out
