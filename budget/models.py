from dataclasses import dataclass


@dataclass
class BudgetEntry:
    date: str
    amount: float
    type: str  # 'income' | 'expense'
    category: str
    description: str | None = None
    is_recurring: int = 0
    recurring_day: int | None = None
    source: str = "manual"
    id: int | None = None
    created_at: str | None = None


@dataclass
class BudgetCategory:
    name: str
    type: str  # 'income' | 'expense' | 'both'
    icon: str | None = None
    budget_limit: float | None = None
    is_default: int = 1
    sort_order: int = 0
    id: int | None = None


@dataclass
class MonthlySummary:
    year_month: str
    total_income: float = 0.0
    total_expense: float = 0.0
    savings: float = 0.0
    savings_rate: float = 0.0
    investable_amount: float = 0.0
    ai_report: str | None = None
    id: int | None = None
