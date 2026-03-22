from db.database import get_connection
from budget.models import BudgetEntry, BudgetCategory


class BudgetManager:
    """가계부 CRUD 관리"""

    # --- Entry CRUD ---
    def add_entry(self, entry: BudgetEntry) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO budget_entries (date, amount, type, category, description, is_recurring, recurring_day, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry.date, entry.amount, entry.type, entry.category,
             entry.description, entry.is_recurring, entry.recurring_day, entry.source),
        )
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id

    def delete_entry(self, entry_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM budget_entries WHERE id=?", (entry_id,))
        conn.commit()
        conn.close()

    def get_entries(
        self,
        year_month: str | None = None,
        category: str | None = None,
        entry_type: str | None = None,
        limit: int = 100,
    ) -> list[BudgetEntry]:
        conn = get_connection()
        query = "SELECT * FROM budget_entries WHERE 1=1"
        params = []

        if year_month:
            query += " AND date LIKE ?"
            params.append(f"{year_month}%")
        if category:
            query += " AND category=?"
            params.append(category)
        if entry_type:
            query += " AND type=?"
            params.append(entry_type)

        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [
            BudgetEntry(
                id=r["id"], date=r["date"], amount=r["amount"], type=r["type"],
                category=r["category"], description=r["description"],
                is_recurring=r["is_recurring"], recurring_day=r["recurring_day"],
                source=r["source"], created_at=r["created_at"],
            )
            for r in rows
        ]

    def add_entries_batch(self, entries: list[dict]) -> int:
        """일괄 입력 (CSV 업로드용)"""
        conn = get_connection()
        count = 0
        for e in entries:
            conn.execute(
                """INSERT INTO budget_entries (date, amount, type, category, description, source)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (e["date"], e["amount"], e["type"], e.get("category", "기타지출"),
                 e.get("description", ""), e.get("source", "csv")),
            )
            count += 1
        conn.commit()
        conn.close()
        return count

    # --- Category CRUD ---
    def get_categories(self, entry_type: str | None = None) -> list[BudgetCategory]:
        conn = get_connection()
        if entry_type:
            rows = conn.execute(
                "SELECT * FROM budget_categories WHERE type=? OR type='both' ORDER BY sort_order",
                (entry_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM budget_categories ORDER BY type, sort_order"
            ).fetchall()
        conn.close()
        return [
            BudgetCategory(
                id=r["id"], name=r["name"], type=r["type"], icon=r["icon"],
                budget_limit=r["budget_limit"], is_default=r["is_default"],
                sort_order=r["sort_order"],
            )
            for r in rows
        ]

    def add_category(self, category: BudgetCategory) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR IGNORE INTO budget_categories (name, type, icon, budget_limit, is_default, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (category.name, category.type, category.icon, category.budget_limit,
             0, category.sort_order),
        )
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id

    def update_category_budget(self, category_name: str, budget_limit: float):
        conn = get_connection()
        conn.execute(
            "UPDATE budget_categories SET budget_limit=? WHERE name=?",
            (budget_limit, category_name),
        )
        conn.commit()
        conn.close()

    def delete_category(self, category_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM budget_categories WHERE id=? AND is_default=0", (category_id,))
        conn.commit()
        conn.close()

    # --- Budget Alerts ---
    def get_budget_alerts(self, year_month: str) -> list[dict]:
        """예산 초과 카테고리 목록"""
        conn = get_connection()
        rows = conn.execute(
            """SELECT bc.name, bc.budget_limit, bc.icon,
                      COALESCE(SUM(be.amount), 0) as spent
               FROM budget_categories bc
               LEFT JOIN budget_entries be ON bc.name = be.category
                   AND be.type = 'expense' AND be.date LIKE ?
               WHERE bc.budget_limit IS NOT NULL AND bc.budget_limit > 0
               GROUP BY bc.name
               HAVING spent >= bc.budget_limit * 0.8""",
            (f"{year_month}%",),
        ).fetchall()
        conn.close()
        return [
            {
                "category": r["name"],
                "icon": r["icon"],
                "spent": r["spent"],
                "limit": r["budget_limit"],
                "pct": round(r["spent"] / r["budget_limit"] * 100, 1) if r["budget_limit"] else 0,
            }
            for r in rows
        ]
