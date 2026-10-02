"""Shadow portfolio for the Colmex Pro account: live valuation, P&L, allocation, risk rules."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from core import data_engine

DEFAULT_ACCOUNT = "colmex_pro_usd"
DEFAULT_MAX_SINGLE_PCT = 15.0


def _num(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def category_group(category: str | None) -> str:
    """'Semiconductors / Edge AI' -> 'Semiconductors'."""
    if not category:
        return "Other"
    return category.split("/")[0].strip() or "Other"


@dataclass
class RiskAlert:
    ticker: str
    weight_pct: float
    limit_pct: float

    @property
    def excess_pct(self) -> float:
        return self.weight_pct - self.limit_pct


class PortfolioManager:
    def __init__(self, seed: dict[str, Any] | None = None, account: str = DEFAULT_ACCOUNT):
        seed = seed if seed is not None else data_engine.load_seed_data()
        acct = seed.get("portfolio_state", {}).get("accounts", {}).get(account, {})
        self.account = account
        self.cash: float = _num(acct.get("cash_balance"))
        self.holdings: list[dict[str, Any]] = acct.get("holdings", []) or []
        self.broker_snapshot = {
            "total_value": _num(acct.get("total_value")),
            "total_unrealized_profit": _num(acct.get("total_unrealized_profit")),
        }
        rules = seed.get("investment_rules", {}) or {}
        self.max_single_pct: float = _num(rules.get("max_single_stock_allocation_pct"),
                                          DEFAULT_MAX_SINGLE_PCT)

    @property
    def tickers(self) -> list[str]:
        return [h["ticker"] for h in self.holdings if h.get("ticker")]

    def symbols(self) -> list[tuple[str, str]]:
        """(ticker, market) pairs for tv_screener.fetch_market_data."""
        return [(t, "US") for t in self.tickers]

    # ---------- valuation ----------

    def positions(
        self,
        quotes: pd.DataFrame | None = None,
        categories: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """One row per holding valued at the live price.

        quotes: output of tv_screener.fetch_market_data (falls back to the seed price per ticker).
        categories: {ticker: watchlist category} used for the sector breakdown.
        """
        live = {}
        if quotes is not None and not quotes.empty:
            live = quotes.set_index("ticker").to_dict("index")
        categories = categories or {}

        rows = []
        for h in self.holdings:
            ticker = h.get("ticker")
            if not ticker:
                continue
            qty = _num(h.get("quantity"))
            open_price = _num(h.get("open_price"))
            fee = _num(h.get("fee"))
            q = live.get(ticker, {})

            live_price = _num(q.get("current_price"), default=float("nan"))
            if math.isfinite(live_price) and live_price > 0:
                price, source = live_price, q.get("source", "live")
            else:
                price, source = _num(h.get("current_price")), "seed"

            cost = qty * open_price
            market_value = qty * price
            pl_usd = market_value - cost + fee  # broker net P&L includes commissions
            change = _num(q.get("daily_change_pct"), default=float("nan"))
            day_pl = (market_value - market_value / (1 + change / 100)
                      if math.isfinite(change) and source != "seed" else 0.0)

            rows.append({
                "ticker": ticker,
                "exchange": h.get("exchange", ""),
                "sector": self._sector(ticker, categories, q),
                "quantity": qty,
                "open_price": open_price,
                "current_price": price,
                "daily_change_pct": change if math.isfinite(change) else None,
                "cost_basis": cost,
                "market_value": market_value,
                "fee": fee,
                "pl_usd": pl_usd,
                "pl_pct": (pl_usd / cost * 100) if cost else 0.0,
                "day_pl_usd": day_pl,
                "price_source": source,
                "open_date": h.get("open_date", ""),
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df
        total = df["market_value"].sum() + self.cash
        df["weight_pct"] = df["market_value"] / total * 100 if total else 0.0
        return df.sort_values("market_value", ascending=False).reset_index(drop=True)

    @staticmethod
    def _sector(ticker: str, categories: dict[str, str], quote: dict[str, Any]) -> str:
        if ticker in categories:
            return category_group(categories[ticker])
        if quote.get("asset_type") == "fund":
            return "ETFs"
        sector = quote.get("sector")
        return sector if isinstance(sector, str) and sector else "Other"

    def summary(self, positions: pd.DataFrame) -> dict[str, float]:
        if positions.empty:
            return {"market_value": 0.0, "cash": self.cash, "total_value": self.cash,
                    "cost_basis": 0.0, "pl_usd": 0.0, "pl_pct": 0.0, "day_pl_usd": 0.0,
                    "positions": 0}
        mv = float(positions["market_value"].sum())
        cost = float(positions["cost_basis"].sum())
        pl = float(positions["pl_usd"].sum())
        return {
            "market_value": mv,
            "cash": self.cash,
            "total_value": mv + self.cash,
            "cost_basis": cost,
            "pl_usd": pl,
            "pl_pct": pl / cost * 100 if cost else 0.0,
            "day_pl_usd": float(positions["day_pl_usd"].sum()),
            "positions": int(len(positions)),
        }

    # ---------- allocation & risk ----------

    def sector_allocation(self, positions: pd.DataFrame, include_cash: bool = True) -> pd.DataFrame:
        if positions.empty:
            return pd.DataFrame(columns=["sector", "market_value", "weight_pct"])
        alloc = (positions.groupby("sector", as_index=False)["market_value"].sum())
        if include_cash and self.cash > 0:
            alloc = pd.concat([alloc, pd.DataFrame([{"sector": "Cash", "market_value": self.cash}])],
                              ignore_index=True)
        total = alloc["market_value"].sum()
        alloc["weight_pct"] = alloc["market_value"] / total * 100 if total else 0.0
        return alloc.sort_values("market_value", ascending=False).reset_index(drop=True)

    def risk_check(self, positions: pd.DataFrame) -> list[RiskAlert]:
        """Flag any single position whose weight exceeds max_single_stock_allocation_pct."""
        if positions.empty:
            return []
        over = positions[positions["weight_pct"] > self.max_single_pct]
        return [RiskAlert(r.ticker, float(r.weight_pct), self.max_single_pct)
                for r in over.itertuples()]
