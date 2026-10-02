"""CapitalPilot AI — Streamlit dashboard (Hebrew RTL, dark theme).

Run:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from core import data_engine, tv_screener
from core.portfolio_manager import PortfolioManager, category_group

st.set_page_config(page_title="CapitalPilot AI", page_icon="📈", layout="wide")

# Status colors (good / critical) — always paired with a ▲/▼ sign, never color alone.
GAIN = "#0ca30c"
LOSS = "#e66767"
# Categorical slots, dark-surface steps (fixed order, never cycled).
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
OTHER_COLOR = "#6b6a65"

TYPE_LABELS = {"income": "הכנסה", "expense": "הוצאה", "investment": "השקעה"}
PAYMENT_METHODS = {
    "credit_card": "כרטיס אשראי",
    "bank_transfer": "העברה בנקאית",
    "cash": "מזומן",
    "bit": "ביט",
}

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&display=swap');
    html, body, [class*="css"], .stApp { font-family: 'Heebo', sans-serif; }
    .stApp, [data-testid="stSidebar"], [data-testid="stMarkdownContainer"],
    [data-testid="stForm"], .stTabs, [data-testid="stMetric"],
    [data-testid="stAlert"], label, .stRadio, .stSelectbox, .stTextInput, .stNumberInput {
        direction: rtl; text-align: right;
    }
    /* Grids, charts and numeric inputs read left-to-right. */
    [data-testid="stDataFrame"], [data-testid="stVegaLiteChart"], input[type="number"] {
        direction: ltr;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background: #1f1f1d; border-radius: 8px 8px 0 0; padding: 8px 18px;
    }
    [data-testid="stMetric"] {
        background: #1f1f1d; border: 1px solid #2c2c2a; border-radius: 12px; padding: 14px 18px;
    }
    [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
    /* Signed numbers must stay LTR inside the RTL markdown containers. */
    [data-testid="stMetricValue"] [data-testid="stMarkdownContainer"],
    [data-testid="stMetricDelta"] [data-testid="stMarkdownContainer"] {
        direction: ltr; unicode-bidi: isolate;
    }
    h1, h2, h3 { letter-spacing: -0.01em; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- cached loaders (ttl=60s) ----------

@st.cache_data(ttl=60, show_spinner=False)
def load_watchlist() -> pd.DataFrame:
    return pd.DataFrame(data_engine.fetch_watchlist(active_only=True))


@st.cache_data(ttl=60, show_spinner="שולף נתוני שוק חיים...")
def load_quotes(symbols: tuple[tuple[str, str], ...]) -> pd.DataFrame:
    return tv_screener.fetch_market_data(symbols)


@st.cache_data(ttl=60, show_spinner=False)
def load_seed() -> dict:
    return data_engine.load_seed_data()


@st.cache_data(ttl=60, show_spinner=False)
def load_budget_categories() -> pd.DataFrame:
    return pd.DataFrame(data_engine.fetch_budget_categories())


@st.cache_data(ttl=60, show_spinner=False)
def load_cashflow() -> pd.DataFrame:
    return pd.DataFrame(data_engine.fetch_cashflow_transactions(limit=500))


# ---------- helpers ----------

def fmt_usd(v: float, signed: bool = False) -> str:
    sign = "+" if signed and v > 0 else ("-" if v < 0 else "")
    return f"{sign}${abs(v):,.2f}"


def ltr(text: str) -> str:
    """Bidi-isolate a number/currency for Hebrew markdown text.

    '$' is escaped because Streamlit markdown treats $...$ as LaTeX.
    """
    return f"⁦{text.replace('$', chr(92) + '$')}⁩"


def arrow(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"▲ {v:+.2f}%" if v > 0 else (f"▼ {v:+.2f}%" if v < 0 else f"{v:.2f}%")


def color_signed(v) -> str:
    if v is None or pd.isna(v) or v == 0:
        return ""
    return f"color: {GAIN if v > 0 else LOSS}; font-weight: 600"


def safe_load(loader, label: str) -> pd.DataFrame:
    try:
        return loader()
    except Exception as exc:
        st.error(f"שגיאה בטעינת {label}: {exc}")
        return pd.DataFrame()


# ---------- header ----------

st.title("CapitalPilot AI")
st.caption("דשבורד השקעות ותזרים · נתוני שוק: TradingView, גיבוי: yfinance · מטמון 60 שניות")

tab_watch, tab_portfolio, tab_budget = st.tabs(
    ["🔭 רשימת מעקב", "💼 תיק מסחר חי · Colmex Pro", "🧾 תזרים ותקציב"]
)

watchlist_df = safe_load(load_watchlist, "רשימת המעקב")
category_by_ticker = (
    dict(zip(watchlist_df["ticker"], watchlist_df["category"])) if not watchlist_df.empty else {}
)

# ======================= Tab 1: Watchlist Hub =======================
with tab_watch:
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.subheader("Watchlist Hub")
    with head_r:
        if st.button("🔄 רענן מחירי שוק כעת", type="primary", width="stretch"):
            with st.spinner("מעדכן מחירים ב-Supabase..."):
                try:
                    summary = tv_screener.refresh_watchlist_prices()
                    load_watchlist.clear()
                    load_quotes.clear()
                    st.session_state["refresh_msg"] = (
                        f"עודכנו {summary['updated']} מתוך {summary['total']} ניירות.",
                        summary["missing"],
                    )
                except Exception as exc:
                    st.session_state["refresh_msg"] = (f"הרענון נכשל: {exc}", [])
            st.rerun()

    if msg := st.session_state.pop("refresh_msg", None):
        text, missing = msg
        if text.startswith("הרענון נכשל"):
            st.error(text)
        else:
            st.success(text)
        if missing:
            st.info("לא נמצא ציטוט עבור: " + ", ".join(missing))

    if watchlist_df.empty:
        st.warning("רשימת המעקב ריקה או שלא ניתן היה לטעון אותה.")
    else:
        wl = watchlist_df.copy()
        wl["group"] = wl["category"].map(category_group)

        symbols = tuple(zip(wl["ticker"], wl["market"].fillna("US")))
        try:
            quotes = load_quotes(symbols)
        except Exception as exc:
            st.warning(f"נתוני שוק חיים אינם זמינים כרגע ({exc}); מוצגים המחירים השמורים.")
            quotes = pd.DataFrame(columns=tv_screener.RESULT_COLUMNS)

        wl = wl.merge(
            quotes[["ticker", "current_price", "daily_change_pct", "pe_ratio", "peg_ratio"]],
            on="ticker", how="left", suffixes=("_db", ""),
        )
        # Prefer the live quote; fall back to the last value persisted in Supabase.
        wl["current_price"] = wl["current_price"].fillna(wl["current_price_db"])
        wl["daily_change_pct"] = wl["daily_change_pct"].fillna(wl["daily_change_pct_db"])

        f1, f2, f3 = st.columns([2, 2, 1])
        groups = sorted(wl["group"].dropna().unique())
        sel_groups = f1.multiselect("קבוצת קטגוריות", groups, placeholder="כל הקבוצות")
        cats_pool = wl[wl["group"].isin(sel_groups)] if sel_groups else wl
        sel_cats = f2.multiselect(
            "קטגוריה", sorted(cats_pool["category"].dropna().unique()), placeholder="כל הקטגוריות"
        )
        search = f3.text_input("חיפוש טיקר / שם / תזה")

        view = cats_pool
        if sel_cats:
            view = view[view["category"].isin(sel_cats)]
        if search:
            s = search.strip().lower()
            view = view[
                view["ticker"].str.lower().str.contains(s, regex=False)
                | view["name"].fillna("").str.lower().str.contains(s, regex=False)
                | view["thesis"].fillna("").str.lower().str.contains(s, regex=False)
            ]

        m1, m2, m3, m4 = st.columns(4)
        chg = view["daily_change_pct"].dropna()
        m1.metric("ניירות מוצגים", f"{len(view)}")
        m2.metric("עולים היום", f"▲ {(chg > 0).sum()}")
        m3.metric("יורדים היום", f"▼ {(chg < 0).sum()}")
        m4.metric("שינוי יומי ממוצע", arrow(chg.mean() if len(chg) else None))

        table = view[[
            "ticker", "name", "market", "category", "current_price", "daily_change_pct",
            "pe_ratio", "peg_ratio", "target_entry_price", "thesis", "last_updated_at",
        ]].copy()
        table["last_updated_at"] = pd.to_datetime(table["last_updated_at"], errors="coerce", utc=True)
        # Supabase returns None for empty numerics; coerce to NaN so na_rep renders "—".
        num_cols = ["current_price", "daily_change_pct", "pe_ratio", "peg_ratio", "target_entry_price"]
        table[num_cols] = table[num_cols].apply(pd.to_numeric, errors="coerce")

        # Styler output overrides column_config number formats, so format here.
        styled = table.style.map(color_signed, subset=["daily_change_pct"]).format({
            "current_price": "{:,.2f}",
            "daily_change_pct": arrow,
            "pe_ratio": "{:.1f}",
            "peg_ratio": "{:.2f}",
            "target_entry_price": "{:,.2f}",
            "last_updated_at": lambda t: "" if pd.isna(t) else t.strftime("%d/%m %H:%M"),
        }, na_rep="—")
        st.dataframe(
            styled,
            hide_index=True,
            width="stretch",
            height=560,
            column_config={
                "ticker": st.column_config.TextColumn("טיקר", pinned=True),
                "name": "שם",
                "market": "שוק",
                "category": "קטגוריה",
                "current_price": "מחיר",
                "daily_change_pct": "שינוי יומי",
                "pe_ratio": "P/E",
                "peg_ratio": "PEG",
                "target_entry_price": "מחיר כניסה יעד",
                "thesis": st.column_config.TextColumn("תזת השקעה", width="large"),
                "last_updated_at": "עודכן ב-DB",
            },
        )
        st.caption("מחירי TASE מוצגים בש\"ח; שאר המחירים בדולר. P/E ו-PEG אינם רלוונטיים לתעודות סל.")

# ======================= Tab 2: Colmex Pro Portfolio =======================
with tab_portfolio:
    st.subheader("Colmex Pro Portfolio")
    try:
        pm = PortfolioManager(load_seed())
    except Exception as exc:
        st.error(f"לא ניתן לקרוא את seed_data.json: {exc}")
        st.stop()

    try:
        pf_quotes = load_quotes(tuple(pm.symbols()))
    except Exception as exc:
        st.warning(f"נתוני שוק חיים אינם זמינים ({exc}); התיק מוערך לפי המחירים השמורים.")
        pf_quotes = None

    positions = pm.positions(pf_quotes, category_by_ticker)
    summ = pm.summary(positions)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("שווי תיק כולל", fmt_usd(summ["total_value"]),
              delta=f"{fmt_usd(summ['day_pl_usd'], signed=True)} היום")
    c2.metric("מזומן זמין", fmt_usd(summ["cash"]))
    c3.metric("רווח/הפסד לא ממומש", fmt_usd(summ["pl_usd"], signed=True),
              delta=f"{summ['pl_pct']:+.2f}%")
    c4.metric("פוזיציות פתוחות", f"{summ['positions']}",
              delta=f"עלות {fmt_usd(summ['cost_basis'])}", delta_color="off")

    alerts = pm.risk_check(positions)
    if alerts:
        for a in alerts:
            st.warning(
                f"⚠️ חריגת סיכון: {a.ticker} מהווה {a.weight_pct:.1f}% מהתיק "
                f"(מגבלה {a.limit_pct:.0f}%, חריגה של {a.excess_pct:.1f}%)."
            )
    else:
        st.success(f"✅ אין פוזיציה בודדת מעל {pm.max_single_pct:.0f}% מהתיק.")

    if (positions["price_source"] == "seed").any():
        stale = positions.loc[positions["price_source"] == "seed", "ticker"].tolist()
        st.caption("ללא מחיר חי (מחיר שמור מ-seed): " + ", ".join(stale))

    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### פוזיציות")
        pos_table = positions[[
            "ticker", "sector", "quantity", "open_price", "current_price", "daily_change_pct",
            "market_value", "pl_usd", "pl_pct", "weight_pct",
        ]]
        st.dataframe(
            pos_table.style.map(color_signed, subset=["daily_change_pct", "pl_usd", "pl_pct"]).format({
                "quantity": "{:,.0f}",
                "open_price": "${:,.2f}",
                "current_price": "${:,.2f}",
                "daily_change_pct": arrow,
                "market_value": "${:,.2f}",
                "pl_usd": lambda v: fmt_usd(v, signed=True),
                "pl_pct": arrow,
                "weight_pct": "{:.1f}%",
            }, na_rep="—"),
            hide_index=True,
            width="stretch",
            height=35 * (len(pos_table) + 1) + 3,
            column_config={
                "ticker": st.column_config.TextColumn("טיקר", pinned=True),
                "sector": "סקטור",
                "quantity": "כמות",
                "open_price": "מחיר פתיחה",
                "current_price": "מחיר נוכחי",
                "daily_change_pct": "יומי",
                "market_value": "שווי שוק",
                "pl_usd": "רווח/הפסד $",
                "pl_pct": "רווח/הפסד %",
                "weight_pct": "משקל",
            },
        )

    with right:
        st.markdown("#### חלוקה לפי סקטורים")
        alloc = pm.sector_allocation(positions)
        # Eight categorical slots max; the tail folds into "Other".
        if len(alloc) > len(SERIES):
            head = alloc.iloc[: len(SERIES) - 1]
            tail = alloc.iloc[len(SERIES) - 1:]
            alloc = pd.concat([head, pd.DataFrame([{
                "sector": "Other",
                "market_value": tail["market_value"].sum(),
                "weight_pct": tail["weight_pct"].sum(),
            }])], ignore_index=True)
        domain = alloc["sector"].tolist()
        colors = [OTHER_COLOR if s == "Other" else SERIES[i] for i, s in enumerate(domain)]

        donut = (
            alt.Chart(alloc)
            .mark_arc(innerRadius=70, cornerRadius=4, stroke="#141413", strokeWidth=2)
            .encode(
                theta=alt.Theta("market_value:Q", stack=True),
                color=alt.Color(
                    "sector:N",
                    scale=alt.Scale(domain=domain, range=colors),
                    sort=domain,
                    legend=alt.Legend(title=None, orient="bottom", columns=2,
                                      labelColor="#c3c2b7", labelLimit=220),
                ),
                order=alt.Order("market_value:Q", sort="descending"),
                tooltip=[
                    alt.Tooltip("sector:N", title="סקטור"),
                    alt.Tooltip("market_value:Q", title="שווי", format="$,.2f"),
                    alt.Tooltip("weight_pct:Q", title="משקל %", format=".1f"),
                ],
            )
            .properties(height=360)
            .configure_view(stroke=None)
            .configure(background="transparent")
        )
        st.altair_chart(donut, width="stretch")
        st.dataframe(
            alloc.style.format({"market_value": "${:,.2f}", "weight_pct": "{:.1f}%"}),
            hide_index=True,
            width="stretch",
            column_config={
                "sector": "סקטור",
                "market_value": "שווי",
                "weight_pct": "משקל",
            },
        )

    snap = pm.broker_snapshot
    st.caption(
        f"צילום מצב ברוקר מקובץ ה-seed: שווי {ltr(fmt_usd(snap['total_value']))} · "
        f"רווח לא ממומש {ltr(fmt_usd(snap['total_unrealized_profit'], signed=True))}"
    )

# ======================= Tab 3: Cashflow & Budget =======================
with tab_budget:
    st.subheader("Cashflow & Budget")
    cats = safe_load(load_budget_categories, "קטגוריות התקציב")
    tx = safe_load(load_cashflow, "תנועות התזרים")

    month_start = date.today().replace(day=1)
    if not tx.empty:
        tx["transaction_date"] = pd.to_datetime(tx["transaction_date"], errors="coerce")
        tx["amount"] = pd.to_numeric(tx["amount"], errors="coerce").fillna(0.0)
        month_tx = tx[tx["transaction_date"].dt.date >= month_start]
    else:
        month_tx = pd.DataFrame(columns=["category_id", "category_name", "amount", "transaction_type"])

    income = month_tx.loc[month_tx["transaction_type"] == "income", "amount"].sum()
    expense = month_tx.loc[month_tx["transaction_type"] == "expense", "amount"].sum()
    b1, b2, b3 = st.columns(3)
    b1.metric("הכנסות החודש", f"₪{income:,.0f}")
    b2.metric("הוצאות החודש", f"₪{expense:,.0f}")
    b3.metric("תזרים נטו", f"₪{income - expense:,.0f}",
              delta=f"{'▲' if income >= expense else '▼'} {month_start:%m/%Y}")

    form_col, cats_col = st.columns([2, 3])

    with form_col:
        st.markdown("#### רישום תנועה חדשה")
        tx_type = st.radio("סוג תנועה", ["expense", "income"], horizontal=True,
                           format_func=lambda t: TYPE_LABELS[t])
        # Investment deposits are cash outflows, so they are offered under expense.
        allowed = {"income"} if tx_type == "income" else {"expense", "investment"}
        options = cats[cats["type"].isin(allowed)] if not cats.empty else cats

        with st.form("cashflow_form", clear_on_submit=True):
            if options.empty:
                st.info("אין קטגוריות מתאימות בטבלת budget_categories.")
                cat_id = None
            else:
                cat_id = st.selectbox(
                    "קטגוריה", options["id"].tolist(),
                    format_func=lambda i: options.loc[options["id"] == i, "name"].iloc[0],
                )
            amount = st.number_input("סכום (₪)", min_value=0.0, step=10.0, format="%.2f")
            tx_date = st.date_input("תאריך", value=date.today(), format="DD/MM/YYYY")
            method = st.selectbox("אמצעי תשלום", list(PAYMENT_METHODS),
                                  format_func=PAYMENT_METHODS.get)
            desc = st.text_input("תיאור (אופציונלי)")
            submitted = st.form_submit_button("💾 שמור תנועה", type="primary", width="stretch")

        if submitted:
            if cat_id is None:
                st.error("יש לבחור קטגוריה.")
            elif amount <= 0:
                st.error("הסכום חייב להיות גדול מאפס.")
            else:
                try:
                    data_engine.insert_cashflow_transaction(
                        category_id=int(cat_id),
                        category_name=options.loc[options["id"] == cat_id, "name"].iloc[0],
                        amount=amount,
                        transaction_type=tx_type,
                        description=desc,
                        payment_method=method,
                        transaction_date=tx_date,
                    )
                    load_cashflow.clear()
                    st.toast(f"נשמרה {TYPE_LABELS[tx_type]} על סך ₪{amount:,.2f}", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(f"השמירה נכשלה: {exc}")

    with cats_col:
        st.markdown("#### קטגוריות תקציב — החודש")
        if cats.empty:
            st.info("לא נמצאו קטגוריות.")
        else:
            actual = month_tx.groupby("category_id")["amount"].sum() if not month_tx.empty else pd.Series(dtype=float)
            budget = cats[["id", "name", "type", "monthly_budget_target", "is_fixed"]].copy()
            budget["monthly_budget_target"] = pd.to_numeric(
                budget["monthly_budget_target"], errors="coerce").fillna(0.0)
            budget["actual"] = budget["id"].map(actual).fillna(0.0)
            budget["remaining"] = budget["monthly_budget_target"] - budget["actual"]
            budget["type"] = budget["type"].map(TYPE_LABELS).fillna(budget["type"])
            st.dataframe(
                budget.drop(columns="id"),
                hide_index=True,
                width="stretch",
                column_config={
                    "name": "קטגוריה",
                    "type": "סוג",
                    "monthly_budget_target": st.column_config.NumberColumn("יעד חודשי", format="₪%.0f"),
                    "is_fixed": st.column_config.CheckboxColumn("קבועה"),
                    "actual": st.column_config.NumberColumn("בפועל", format="₪%.0f"),
                    "remaining": st.column_config.NumberColumn("יתרה", format="₪%.0f"),
                },
            )

    st.markdown("#### תנועות אחרונות")
    if tx.empty:
        st.info("עדיין לא נרשמו תנועות.")
    else:
        recent = tx[["transaction_date", "transaction_type", "category_name", "amount",
                     "payment_method", "description"]].head(50).copy()
        recent["transaction_type"] = recent["transaction_type"].map(TYPE_LABELS)
        recent["payment_method"] = recent["payment_method"].map(PAYMENT_METHODS).fillna("")
        st.dataframe(
            recent,
            hide_index=True,
            width="stretch",
            column_config={
                "transaction_date": st.column_config.DateColumn("תאריך", format="DD/MM/YYYY"),
                "transaction_type": "סוג",
                "category_name": "קטגוריה",
                "amount": st.column_config.NumberColumn("סכום", format="₪%.2f"),
                "payment_method": "אמצעי תשלום",
                "description": "תיאור",
            },
        )
