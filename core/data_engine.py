"""Data access layer: Supabase client, seed_data.json, watchlist and cashflow tables."""
from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = PROJECT_ROOT / "seed_data.json"

load_dotenv(PROJECT_ROOT / ".env")


@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY are missing from .env")
    return create_client(url, key)


# ---------- seed_data.json ----------

def load_seed_data(path: Path = SEED_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------- watchlist ----------

def fetch_watchlist(active_only: bool = True) -> list[dict[str, Any]]:
    query = get_client().table("watchlist").select("*").order("id")
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data or []


def batch_update_watchlist_prices(rows: list[dict[str, Any]], chunk_size: int = 100) -> int:
    """Upsert current_price / daily_change_pct / last_updated_at keyed on ticker.

    Each row must contain: ticker, current_price, daily_change_pct, last_updated_at.
    Only the supplied columns are touched on existing rows.
    """
    if not rows:
        return 0
    table = get_client().table("watchlist")
    updated = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        table.upsert(chunk, on_conflict="ticker").execute()
        updated += len(chunk)
    return updated


# ---------- budget & cashflow ----------

def fetch_budget_categories() -> list[dict[str, Any]]:
    return get_client().table("budget_categories").select("*").order("id").execute().data or []


def fetch_cashflow_transactions(limit: int = 200) -> list[dict[str, Any]]:
    return (
        get_client().table("cashflow_transactions").select("*")
        .order("transaction_date", desc=True).order("id", desc=True)
        .limit(limit).execute().data or []
    )


def insert_cashflow_transaction(
    category_id: int | None,
    category_name: str,
    amount: float,
    transaction_type: str,
    description: str = "",
    payment_method: str | None = None,
    transaction_date: date | None = None,
) -> dict[str, Any]:
    if transaction_type not in ("income", "expense"):
        raise ValueError("transaction_type must be 'income' or 'expense'")
    if amount <= 0:
        raise ValueError("amount must be positive")
    payload = {
        "category_id": category_id,
        "category_name": category_name,
        "amount": round(float(amount), 2),
        "transaction_type": transaction_type,
        "description": description or None,
        "payment_method": payment_method,
        "transaction_date": (transaction_date or date.today()).isoformat(),
    }
    res = get_client().table("cashflow_transactions").insert(payload).execute()
    return (res.data or [payload])[0]
