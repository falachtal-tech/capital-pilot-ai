-- 1. טבלת רשימת מעקב (Watchlist)
CREATE TABLE IF NOT EXISTS watchlist (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    market VARCHAR(10) DEFAULT 'US',
    category VARCHAR(100),
    thesis TEXT,
    target_entry_price NUMERIC,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. טבלת עסקאות ותיק מסחר פעיל (Trading Transactions)
CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id BIGSERIAL PRIMARY KEY,
    account VARCHAR(50) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL,
    quantity NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    stop_loss NUMERIC,
    take_profit NUMERIC,
    transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. טבלת חסכונות פנסיוניים (Long-Term Assets)
CREATE TABLE IF NOT EXISTS pension_assets (
    id BIGSERIAL PRIMARY KEY,
    asset_type VARCHAR(50) NOT NULL,
    provider VARCHAR(100),
    track VARCHAR(100),
    current_balance NUMERIC DEFAULT 0,
    monthly_deposit NUMERIC DEFAULT 0,
    fee_accumulation_pct NUMERIC DEFAULT 0,
    fee_deposit_pct NUMERIC DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. טבלת יעדים והפקדות שנתיות (Goals & Deposits)
CREATE TABLE IF NOT EXISTS wealth_goals (
    id BIGSERIAL PRIMARY KEY,
    year INT NOT NULL UNIQUE,
    annual_deposit_goal NUMERIC NOT NULL,
    target_annual_return_pct NUMERIC NOT NULL,
    actual_deposit_ytd NUMERIC DEFAULT 0
);