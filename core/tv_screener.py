"""Market scanner: live price / daily change / P/E / PEG from TradingView, yfinance fallback.

Flow:
    fetch_watchlist() -> fetch_market_data() -> batch_update_watchlist_prices()
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd
from tradingview_screener import Column, Query

from core import data_engine

log = logging.getLogger(__name__)

TV_COLUMNS = [
    "name", "exchange", "close", "change", "currency",
    "price_earnings_ttm", "price_earnings_growth_ttm", "sector", "type",
]
# When a symbol is listed on several venues, prefer the primary listing.
EXCHANGE_PRIORITY = {"NASDAQ": 0, "NYSE": 1, "AMEX": 2, "CBOE": 3, "TASE": 0, "OTC": 9}
# TASE quotes arrive in agorot (ILA); convert to shekels.
SUBUNIT_CURRENCIES = {"ILA": 100}

RESULT_COLUMNS = [
    "ticker", "current_price", "daily_change_pct", "pe_ratio", "peg_ratio",
    "sector", "asset_type", "currency", "source",
]


def _clean(value: Any) -> float | None:
    """Return a finite float or None (TradingView/yfinance may return NaN/None)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def resolve_symbol(ticker: str, market: str | None) -> tuple[str, str]:
    """Map a watchlist ticker to (tradingview market, tradingview symbol name).

    Dual-listed names (market 'US/TASE') are priced on the US listing in USD.
    """
    t = (ticker or "").strip().upper()
    m = (market or "US").replace(" ", "").upper()
    if t.endswith(".TA") or m == "TASE":
        return "israel", t.removesuffix(".TA")
    return "america", t


def _yf_symbol(ticker: str, tv_market: str, tv_name: str) -> str:
    if tv_market == "israel":
        return f"{tv_name}.TA"
    return tv_name.replace(".", "-")  # BRK.B -> BRK-B


# ---------- TradingView ----------

def _fetch_tradingview(tv_market: str, names: list[str]) -> pd.DataFrame:
    q = (
        Query().select(*TV_COLUMNS)
        .where(Column("name").isin(names))
        .set_markets(tv_market)
        .limit(max(len(names) * 3, 50))
    )
    # The default query only returns common stocks; drop it so ETFs/funds are included.
    q.query.pop("filter2", None)
    _, df = q.get_scanner_data()
    if df.empty:
        return df
    df = df.assign(_prio=df["exchange"].map(EXCHANGE_PRIORITY).fillna(5))
    return df.sort_values("_prio").drop_duplicates("name", keep="first")


def _tv_rows(df: pd.DataFrame, by_name: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for rec in df.to_dict("records"):
        ticker = by_name.get(str(rec.get("name", "")).upper())
        if not ticker:
            continue
        currency = rec.get("currency") or ""
        divisor = SUBUNIT_CURRENCIES.get(currency, 1)
        price = _clean(rec.get("close"))
        rows.append({
            "ticker": ticker,
            "current_price": round(price / divisor, 4) if price is not None else None,
            "daily_change_pct": _clean(rec.get("change")),
            "pe_ratio": _clean(rec.get("price_earnings_ttm")),
            "peg_ratio": _clean(rec.get("price_earnings_growth_ttm")),
            "sector": rec.get("sector") or None,
            "asset_type": rec.get("type") or None,
            "currency": "ILS" if currency == "ILA" else (currency or None),
            "source": "tradingview",
        })
    return rows


# ---------- yfinance fallback ----------

def _fetch_yfinance(symbols: dict[str, str]) -> list[dict[str, Any]]:
    """symbols: {watchlist_ticker: yfinance_symbol}. Price + daily change only."""
    if not symbols:
        return []
    import yfinance as yf

    yf_list = list(dict.fromkeys(symbols.values()))
    try:
        data = yf.download(yf_list, period="5d", progress=False, auto_adjust=False,
                           group_by="ticker", threads=True)
    except Exception as exc:  # network / rate limit
        log.warning("yfinance fallback failed: %s", exc)
        return []
    if data is None or data.empty:
        return []

    rows = []
    for ticker, yf_sym in symbols.items():
        try:
            closes = (data[yf_sym]["Close"] if isinstance(data.columns, pd.MultiIndex)
                      else data["Close"]).dropna()
        except KeyError:
            continue
        if closes.empty:
            continue
        last = _clean(closes.iloc[-1])
        prev = _clean(closes.iloc[-2]) if len(closes) > 1 else None
        divisor = 100 if yf_sym.endswith(".TA") else 1  # TASE quotes in agorot
        rows.append({
            "ticker": ticker,
            "current_price": round(last / divisor, 4) if last is not None else None,
            "daily_change_pct": ((last / prev - 1) * 100) if last and prev else None,
            "pe_ratio": None,
            "peg_ratio": None,
            "sector": None,
            "asset_type": None,
            "currency": "ILS" if divisor == 100 else "USD",
            "source": "yfinance",
        })
    return rows


# ---------- public API ----------

def fetch_market_data(symbols: Iterable[tuple[str, str | None]]) -> pd.DataFrame:
    """Fetch live quotes for [(ticker, market), ...].

    TradingView first (batched per market); any ticker it misses, or every ticker
    if TradingView raises, is retried through yfinance.
    """
    groups: dict[str, dict[str, str]] = {}   # tv_market -> {tv_name: ticker}
    yf_symbols: dict[str, str] = {}
    for ticker, market in symbols:
        if not ticker:
            continue
        tv_market, tv_name = resolve_symbol(ticker, market)
        groups.setdefault(tv_market, {})[tv_name] = ticker
        yf_symbols[ticker] = _yf_symbol(ticker, tv_market, tv_name)

    rows: list[dict[str, Any]] = []
    for tv_market, by_name in groups.items():
        try:
            df = _fetch_tradingview(tv_market, list(by_name))
            rows.extend(_tv_rows(df, by_name))
        except Exception as exc:
            log.warning("TradingView fetch failed for %s: %s", tv_market, exc)

    found = {r["ticker"] for r in rows if r["current_price"] is not None}
    missing = {t: s for t, s in yf_symbols.items() if t not in found}
    if missing:
        rows = [r for r in rows if r["ticker"] not in missing] + _fetch_yfinance(missing)

    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


def refresh_watchlist_prices() -> dict[str, Any]:
    """Read active watchlist tickers, fetch live data, batch-update Supabase.

    Returns a summary with the fetched DataFrame and the tickers that had no quote.
    """
    watchlist = data_engine.fetch_watchlist(active_only=True)
    quotes = fetch_market_data((w.get("ticker"), w.get("market")) for w in watchlist)

    now = datetime.now(timezone.utc).isoformat()
    updates = []
    for r in quotes.to_dict("records"):
        price = _clean(r.get("current_price"))
        if price is None:
            continue
        change = _clean(r.get("daily_change_pct"))  # DataFrame turns None into NaN
        updates.append({
            "ticker": r["ticker"],
            "current_price": price,
            "daily_change_pct": round(change, 4) if change is not None else None,
            "last_updated_at": now,
        })
    updated = data_engine.batch_update_watchlist_prices(updates)

    quoted = {u["ticker"] for u in updates}
    return {
        "updated": updated,
        "total": len(watchlist),
        "missing": sorted(w["ticker"] for w in watchlist if w.get("ticker") not in quoted),
        "quotes": quotes,
        "timestamp": now,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = refresh_watchlist_prices()
    print(f"Updated {summary['updated']}/{summary['total']} tickers at {summary['timestamp']}")
    if summary["missing"]:
        print("No quote for:", ", ".join(summary["missing"]))
