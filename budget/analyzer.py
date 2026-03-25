import pandas as pd
from datetime import datetime, timedelta
from budget.manager import BudgetManager
from budget.models import MonthlySummary
from db.database import get_connection
from utils.constants import INVESTABLE_SAVINGS_RATIO


class BudgetAnalyzer:
    """가계부 분석 엔진"""

    def __init__(self):
        self.manager = BudgetManager()

    def get_monthly_summary(self, year_month: str) -> MonthlySummary:
        """월별 수입/지출 요약"""
        conn = get_connection()
        income = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM budget_entries WHERE type='income' AND date LIKE ?",
            (f"{year_month}%",),
        ).fetchone()[0]
        expense = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM budget_entries WHERE type='expense' AND date LIKE ?",
            (f"{year_month}%",),
        ).fetchone()[0]
        conn.close()

        savings = income - expense
        savings_rate = (savings / income * 100) if income > 0 else 0
        investable = max(0, savings * INVESTABLE_SAVINGS_RATIO)

        return MonthlySummary(
            year_month=year_month,
            total_income=income,
            total_expense=expense,
            savings=savings,
            savings_rate=round(savings_rate, 1),
            investable_amount=round(investable, 0),
        )

    def get_monthly_trend(self, months: int = 12) -> pd.DataFrame:
        """최근 N개월 수입/지출 추이"""
        conn = get_connection()
        rows = conn.execute(
            """SELECT
                 substr(date, 1, 7) as year_month,
                 SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as total_income,
                 SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as total_expense
               FROM budget_entries
               GROUP BY substr(date, 1, 7)
               ORDER BY year_month DESC
               LIMIT ?""",
            (months,),
        ).fetchall()
        conn.close()

        if not rows:
            return pd.DataFrame(columns=["year_month", "total_income", "total_expense", "savings", "savings_rate"])

        data = []
        for r in rows:
            inc = r["total_income"]
            exp = r["total_expense"]
            sav = inc - exp
            rate = (sav / inc * 100) if inc > 0 else 0
            data.append({
                "year_month": r["year_month"],
                "total_income": inc,
                "total_expense": exp,
                "savings": sav,
                "savings_rate": round(rate, 1),
            })

        return pd.DataFrame(data).sort_values("year_month")

    def get_category_breakdown(self, year_month: str) -> pd.DataFrame:
        """카테고리별 지출 비중"""
        conn = get_connection()
        rows = conn.execute(
            """SELECT category, SUM(amount) as amount
               FROM budget_entries
               WHERE type='expense' AND date LIKE ?
               GROUP BY category
               ORDER BY amount DESC""",
            (f"{year_month}%",),
        ).fetchall()
        conn.close()

        if not rows:
            return pd.DataFrame(columns=["category", "amount", "pct"])

        data = [{"category": r["category"], "amount": r["amount"]} for r in rows]
        df = pd.DataFrame(data)
        total = df["amount"].sum()
        df["pct"] = (df["amount"] / total * 100).round(1) if total > 0 else 0
        return df

    def calculate_investable_amount(
        self, year_month: str, emergency_months: int = 3
    ) -> dict:
        """투자 가능 여유자금 계산"""
        summary = self.get_monthly_summary(year_month)
        trend = self.get_monthly_trend(6)

        if trend.empty:
            avg_expense = summary.total_expense
        else:
            avg_expense = trend["total_expense"].mean()

        emergency_reserve = avg_expense * emergency_months
        surplus = summary.savings
        investable = max(0, surplus - (emergency_reserve / 12))

        return {
            "monthly_income": summary.total_income,
            "monthly_expense": summary.total_expense,
            "monthly_savings": summary.savings,
            "savings_rate": summary.savings_rate,
            "avg_monthly_expense": round(avg_expense, 0),
            "emergency_reserve_needed": round(emergency_reserve, 0),
            "investable_amount": round(investable, 0),
        }

    def cache_monthly_summary(self, year_month: str):
        """월별 요약을 DB에 캐시"""
        summary = self.get_monthly_summary(year_month)
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO budget_monthly_summary
               (year_month, total_income, total_expense, savings, savings_rate, investable_amount)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (year_month, summary.total_income, summary.total_expense,
             summary.savings, summary.savings_rate, summary.investable_amount),
        )
        conn.commit()
        conn.close()
