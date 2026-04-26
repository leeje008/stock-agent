import sqlite3
import os
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS portfolio_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            market TEXT NOT NULL CHECK(market IN ('KR', 'US', 'ETF')),
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'KRW',
            sector TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            market TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL')),
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'KRW',
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS optimization_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            weights_json TEXT NOT NULL,
            expected_return REAL,
            volatility REAL,
            sharpe_ratio REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS analysis_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            total_value REAL NOT NULL,
            total_cost REAL NOT NULL,
            holdings_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sentiment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            market_sentiment TEXT,
            sentiment_score REAL,
            ticker_sentiments_json TEXT,
            summary TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS upload_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            broker TEXT,
            total_transactions INTEGER DEFAULT 0,
            inserted_transactions INTEGER DEFAULT 0,
            skipped_duplicates INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS budget_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            category TEXT NOT NULL,
            description TEXT,
            is_recurring INTEGER DEFAULT 0,
            recurring_day INTEGER,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS budget_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense', 'both')),
            icon TEXT,
            budget_limit REAL,
            is_default INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS budget_monthly_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year_month TEXT NOT NULL UNIQUE,
            total_income REAL DEFAULT 0,
            total_expense REAL DEFAULT 0,
            savings REAL DEFAULT 0,
            savings_rate REAL DEFAULT 0,
            investable_amount REAL DEFAULT 0,
            ai_report TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_budget_date ON budget_entries(date);
        CREATE INDEX IF NOT EXISTS idx_budget_category ON budget_entries(category);

        CREATE TABLE IF NOT EXISTS rebalancing_targets (
            ticker TEXT PRIMARY KEY,
            target_weight REAL NOT NULL,
            strategy TEXT,
            set_date TEXT DEFAULT (date('now'))
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            market TEXT NOT NULL,
            name TEXT NOT NULL,
            target_price_low REAL,
            target_price_high REAL,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS isa_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL UNIQUE,
            monthly_contribution REAL NOT NULL DEFAULT 1000000,
            risk_level TEXT NOT NULL DEFAULT '중립',
            start_date TEXT,
            annual_limit REAL NOT NULL DEFAULT 24000000,
            tax_status TEXT NOT NULL DEFAULT 'general',
            note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS monthly_contributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            year_month TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(account_id, year_month),
            FOREIGN KEY (account_id) REFERENCES isa_accounts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS target_allocation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            set_date TEXT NOT NULL,
            weights_json TEXT NOT NULL,
            monthly_amount REAL NOT NULL,
            strategy TEXT NOT NULL,
            reason TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES isa_accounts(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_contrib_yyyymm ON monthly_contributions(year_month);
        CREATE INDEX IF NOT EXISTS idx_target_setdate ON target_allocation_history(set_date);
    """)

    # 기존 transactions 테이블 확장
    for col_sql in [
        "ALTER TABLE transactions ADD COLUMN tx_date TEXT",
        "ALTER TABLE transactions ADD COLUMN fee REAL DEFAULT 0",
        "ALTER TABLE transactions ADD COLUMN tax REAL DEFAULT 0",
    ]:
        try:
            cursor.execute(col_sql)
        except Exception:
            pass  # Column already exists

    conn.commit()
    conn.close()


def init_budget_defaults():
    """기본 가계부 카테고리 초기화"""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM budget_categories").fetchone()[0]
    if count > 0:
        conn.close()
        return

    defaults = [
        ("식비", "expense", "🍚", None, 1, 1),
        ("교통", "expense", "🚌", None, 1, 2),
        ("주거/관리비", "expense", "🏠", None, 1, 3),
        ("쇼핑", "expense", "🛒", None, 1, 4),
        ("의료/건강", "expense", "🏥", None, 1, 5),
        ("교육", "expense", "📚", None, 1, 6),
        ("여가/문화", "expense", "🎬", None, 1, 7),
        ("보험", "expense", "🛡️", None, 1, 8),
        ("통신", "expense", "📱", None, 1, 9),
        ("카페/음료", "expense", "☕", None, 1, 10),
        ("구독서비스", "expense", "📺", None, 1, 11),
        ("경조사", "expense", "💐", None, 1, 12),
        ("기타지출", "expense", "📦", None, 1, 99),
        ("급여", "income", "💰", None, 1, 1),
        ("부수입", "income", "💵", None, 1, 2),
        ("투자수익", "income", "📈", None, 1, 3),
        ("이자", "income", "🏦", None, 1, 4),
        ("기타수입", "income", "💎", None, 1, 99),
    ]

    conn.executemany(
        "INSERT INTO budget_categories (name, type, icon, budget_limit, is_default, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
        defaults,
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
