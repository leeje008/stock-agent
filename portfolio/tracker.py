import json
from datetime import date, timedelta

from db.database import get_connection


class PortfolioTracker:
    def __init__(self):
        self.conn = get_connection()

    def take_snapshot(self, total_value: float, total_cost: float, holdings: list[dict]):
        today = date.today().isoformat()
        holdings_json = json.dumps(holdings, ensure_ascii=False)
        self.conn.execute(
            """INSERT OR REPLACE INTO portfolio_snapshots (date, total_value, total_cost, holdings_json)
               VALUES (?, ?, ?, ?)""",
            (today, total_value, total_cost, holdings_json),
        )
        self.conn.commit()

    def get_history(self, days: int = 90) -> list[dict]:
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT date, total_value, total_cost
               FROM portfolio_snapshots
               WHERE date >= ?
               ORDER BY date ASC""",
            (since,),
        ).fetchall()
        result = []
        for row in rows:
            total_value = row["total_value"]
            total_cost = row["total_cost"]
            pnl = total_value - total_cost
            return_pct = (pnl / total_cost * 100) if total_cost else 0.0
            result.append({
                "date": row["date"],
                "total_value": total_value,
                "total_cost": total_cost,
                "pnl": pnl,
                "return_pct": return_pct,
            })
        return result

    def get_latest_snapshot(self) -> dict | None:
        row = self.conn.execute(
            """SELECT date, total_value, total_cost, holdings_json
               FROM portfolio_snapshots
               ORDER BY date DESC
               LIMIT 1""",
        ).fetchone()
        if row is None:
            return None
        total_value = row["total_value"]
        total_cost = row["total_cost"]
        pnl = total_value - total_cost
        return_pct = (pnl / total_cost * 100) if total_cost else 0.0
        return {
            "date": row["date"],
            "total_value": total_value,
            "total_cost": total_cost,
            "pnl": pnl,
            "return_pct": return_pct,
            "holdings_json": row["holdings_json"],
        }
