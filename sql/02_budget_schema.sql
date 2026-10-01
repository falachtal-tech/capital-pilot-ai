-- 5. טבלת קטגוריות תקציב חודשי (Budget Categories & Targets)
CREATE TABLE IF NOT EXISTS budget_categories (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('income', 'expense', 'investment')),
    monthly_budget_target NUMERIC DEFAULT 0,
    is_fixed BOOLEAN DEFAULT FALSE, -- האם הוצאה קבועה (שכירות, ביטוח) או משתנה (בילויים, קניות)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. טבלת תנועות תזרים מזומנים שוטפות (Cashflow Transactions)
CREATE TABLE IF NOT EXISTS cashflow_transactions (
    id BIGSERIAL PRIMARY KEY,
    category_id BIGINT REFERENCES budget_categories(id) ON DELETE SET NULL,
    category_name VARCHAR(100) NOT NULL,
    amount NUMERIC NOT NULL,
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('income', 'expense')),
    description TEXT,
    payment_method VARCHAR(50), -- 'credit_card', 'bank_transfer', 'cash', 'bit'
    transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. הכנסת קטגוריות בסיס לדוגמה (ניתנות לשינוי ועריכה בעתיד)
INSERT INTO budget_categories (name, type, monthly_budget_target, is_fixed) VALUES
('משכורת / הכנסות עיקריות', 'income', 0, FALSE),
('הכנסות נוספות / פרילנס', 'income', 0, FALSE),
('דיור ושכר דירה', 'expense', 0, TRUE),
('מזון וסופרמרקט', 'expense', 0, FALSE),
('מסעדות ובילויים', 'expense', 0, FALSE),
('רכב ותחבורה', 'expense', 0, FALSE),
('חשבונות (חשמל, מים, ארנונה, תקשורת)', 'expense', 0, TRUE),
('השקעות שוטפות (קולמקס / הפניקס)', 'investment', 0, FALSE)
ON CONFLICT (name) DO NOTHING;