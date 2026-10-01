# CapitalPilot AI - System Guidelines for Claude Code

## Architecture & Technology Stack
- **Language**: Python 3.10+
- **UI & Dashboard**: Streamlit
- **Market Data Engine**: `tradingview-screener` (Primary: US & Israel TASE markets), supplemented by `yfinance`
- **Alerts & Reconciliation**: `python-telegram-bot`
- **Data Persistence**: Local JSON / SQLite synced with `seed_data.json`

## Directory Structure
- `app.py`: Streamlit entry point, dashboard tabs, views, and visual metrics.
- `core/tv_screener.py`: Scanner module polling TradingView public endpoints for live indicators.
- `core/data_engine.py`: Loads, normalizes, and saves watchlist, transactions, and pension balances.
- `core/analytics.py`: Financial logic (Piotroski F-Score, PEG, Free Cash Flow, ATR Stop Loss).
- `core/portfolio.py`: Shadow portfolio manager, deposit pacing vs annual goals, and reconciliation.
- `seed_data.json`: Initial state and baseline configurations.

## Development Rules & Best Practices
1. **Defensive Data Handling**: Market APIs may return NaN, null, or missing fields. Always use `.get()` with sane fallbacks.
2. **Performance**: Wrap all external TradingView and financial fetch calls in `@st.cache_data(ttl=300)` (5-minute TTL).
3. **Dual Market Support**: Support both US tickers (`AAPL`, `NVDA`) and Israeli tickers (`TASE` symbols).
4. **Structured Logic**: Never guess prices or recommendations. Base entry/exit strictly on defined models (ATR, Support/Resistance, Piotroski).