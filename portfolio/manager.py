import json
import sqlite3

from db.database import get_connection
from db.models import Holding, Transaction


class PortfolioManager:
    """포트폴리오 CRUD 관리"""

    def add_holding(self, holding: Holding) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO portfolio_holdings
               (ticker, market, name, quantity, avg_price, currency, sector)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                holding.ticker,
                holding.market,
                holding.name,
                holding.quantity,
                holding.avg_price,
                holding.currency,
                holding.sector,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id

    def update_holding(self, holding_id: int, quantity: int, avg_price: float):
        conn = get_connection()
        conn.execute(
            """UPDATE portfolio_holdings
               SET quantity=?, avg_price=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (quantity, avg_price, holding_id),
        )
        conn.commit()
        conn.close()

    def remove_holding(self, holding_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM portfolio_holdings WHERE id=?", (holding_id,))
        conn.commit()
        conn.close()

    def get_all_holdings(self) -> list[Holding]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM portfolio_holdings").fetchall()
        conn.close()
        return [
            Holding(
                id=r["id"],
                ticker=r["ticker"],
                market=r["market"],
                name=r["name"],
                quantity=r["quantity"],
                avg_price=r["avg_price"],
                currency=r["currency"],
                sector=r["sector"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def get_portfolio_summary(self) -> dict:
        holdings = self.get_all_holdings()
        return {
            "total_holdings": len(holdings),
            "holdings": [
                {
                    "ticker": h.ticker,
                    "market": h.market,
                    "name": h.name,
                    "quantity": h.quantity,
                    "avg_price": h.avg_price,
                    "currency": h.currency,
                    "sector": h.sector,
                }
                for h in holdings
            ],
        }

    def record_transaction(self, tx: Transaction) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO transactions
               (ticker, market, action, quantity, price, currency, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tx.ticker, tx.market, tx.action, tx.quantity, tx.price, tx.currency, tx.note),
        )
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id

    def get_transactions(self, limit: int = 50) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_holding_by_ticker(self, ticker: str):
        """티커로 보유종목 조회"""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM portfolio_holdings WHERE ticker=?", (ticker,)
        ).fetchone()
        conn.close()
        if row:
            return Holding(
                id=row["id"], ticker=row["ticker"], market=row["market"],
                name=row["name"], quantity=row["quantity"], avg_price=row["avg_price"],
                currency=row["currency"], sector=row["sector"],
            )
        return None

    def update_or_merge_holding(self, holding_id: int, quantity: int, avg_price: float):
        """기존 보유종목의 수량과 평균매입가 업데이트"""
        conn = get_connection()
        conn.execute(
            "UPDATE portfolio_holdings SET quantity=?, avg_price=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (quantity, avg_price, holding_id),
        )
        conn.commit()
        conn.close()

    def record_transactions_batch(self, transactions: list[dict]) -> tuple[int, int]:
        """거래내역 일괄 저장 (중복 제외). Returns (inserted, skipped)"""
        conn = get_connection()
        inserted = 0
        skipped = 0

        for tx in transactions:
            # Check duplicate
            existing = conn.execute(
                """SELECT COUNT(*) FROM transactions
                   WHERE ticker=? AND tx_date=? AND quantity=? AND price=? AND action=?""",
                (tx["ticker"], tx["date"], tx["quantity"], tx["price"], tx["action"]),
            ).fetchone()[0]

            if existing > 0:
                skipped += 1
                continue

            conn.execute(
                """INSERT INTO transactions (ticker, market, action, quantity, price, currency, note, tx_date, fee, tax)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tx["ticker"],
                    tx.get("market", "KR"),
                    tx["action"],
                    tx["quantity"],
                    tx["price"],
                    tx.get("currency", "KRW"),
                    tx.get("name", ""),
                    tx["date"],
                    tx.get("fee", 0),
                    tx.get("tax", 0),
                ),
            )
            inserted += 1

        conn.commit()
        conn.close()
        return inserted, skipped

    def record_upload_history(self, filename: str, broker: str, total: int, inserted: int, skipped: int):
        """업로드 이력 저장"""
        conn = get_connection()
        conn.execute(
            "INSERT INTO upload_history (filename, broker, total_transactions, inserted_transactions, skipped_duplicates) VALUES (?, ?, ?, ?, ?)",
            (filename, broker, total, inserted, skipped),
        )
        conn.commit()
        conn.close()

    def get_last_upload_info(self) -> dict | None:
        """마지막 업로드 정보"""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM upload_history ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
