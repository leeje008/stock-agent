from datetime import date
from db.database import get_connection
from budget.models import BudgetEntry
from budget.manager import BudgetManager


class RecurringExpenseManager:
    """고정지출 자동 반영 관리"""

    def __init__(self):
        self.manager = BudgetManager()

    def get_recurring_items(self) -> list[BudgetEntry]:
        """고정지출/수입 목록 조회"""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM budget_entries WHERE is_recurring=1 ORDER BY recurring_day"
        ).fetchall()
        conn.close()
        return [
            BudgetEntry(
                id=r["id"], date=r["date"], amount=r["amount"], type=r["type"],
                category=r["category"], description=r["description"],
                is_recurring=r["is_recurring"], recurring_day=r["recurring_day"],
                source=r["source"],
            )
            for r in rows
        ]

    def add_recurring(self, entry: BudgetEntry) -> int:
        """고정지출/수입 등록"""
        entry.is_recurring = 1
        entry.source = "recurring_template"
        return self.manager.add_entry(entry)

    def remove_recurring(self, entry_id: int):
        """고정지출 삭제"""
        conn = get_connection()
        conn.execute("DELETE FROM budget_entries WHERE id=? AND is_recurring=1", (entry_id,))
        conn.commit()
        conn.close()

    def auto_apply_recurring(self, year_month: str) -> int:
        """해당 월에 고정지출/수입 자동 반영. 이미 반영된 건은 스킵."""
        recurring_items = self.get_recurring_items()
        conn = get_connection()
        applied = 0

        for item in recurring_items:
            day = item.recurring_day or 1
            target_date = f"{year_month}-{day:02d}"

            # Check if already applied
            existing = conn.execute(
                """SELECT COUNT(*) FROM budget_entries
                   WHERE source='recurring_auto' AND category=? AND date=? AND amount=?""",
                (item.category, target_date, item.amount),
            ).fetchone()[0]

            if existing > 0:
                continue

            conn.execute(
                """INSERT INTO budget_entries (date, amount, type, category, description, is_recurring, recurring_day, source)
                   VALUES (?, ?, ?, ?, ?, 0, NULL, 'recurring_auto')""",
                (target_date, item.amount, item.type, item.category,
                 f"[자동] {item.description or item.category}"),
            )
            applied += 1

        conn.commit()
        conn.close()
        return applied
