import yfinance as yf
from db.database import get_connection
from utils.logger import get_logger

logger = get_logger("watchlist")


class WatchlistManager:
    """관심종목 관리"""

    def add(self, ticker: str, market: str, name: str,
            target_price_low: float | None = None,
            target_price_high: float | None = None,
            note: str = ""):
        conn = get_connection()
        conn.execute(
            """INSERT INTO watchlist (ticker, market, name, target_price_low, target_price_high, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker, market, name, target_price_low, target_price_high, note),
        )
        conn.commit()
        conn.close()

    def remove(self, watchlist_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM watchlist WHERE id = ?", (watchlist_id,))
        conn.commit()
        conn.close()

    def get_all(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM watchlist ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def check_alerts(self) -> list[dict]:
        """관심종목 가격 알림 확인"""
        items = self.get_all()
        alerts = []

        for item in items:
            try:
                yf_ticker = f"{item['ticker']}.KS" if item["market"] == "KR" else item["ticker"]
                stock = yf.Ticker(yf_ticker)
                hist = stock.history(period="2d")
                if hist.empty:
                    continue

                current_price = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
                change_pct = (current_price / prev_close - 1) * 100 if prev_close > 0 else 0

                alert_type = None
                if item["target_price_low"] and current_price <= item["target_price_low"]:
                    alert_type = "매수 목표가 도달"
                elif item["target_price_high"] and current_price >= item["target_price_high"]:
                    alert_type = "매도 목표가 도달"

                alerts.append({
                    "id": item["id"],
                    "ticker": item["ticker"],
                    "name": item["name"],
                    "market": item["market"],
                    "current_price": current_price,
                    "change_pct": change_pct,
                    "target_low": item["target_price_low"],
                    "target_high": item["target_price_high"],
                    "note": item["note"],
                    "alert_type": alert_type,
                    "distance_to_low": ((current_price / item["target_price_low"] - 1) * 100)
                        if item["target_price_low"] else None,
                    "distance_to_high": ((item["target_price_high"] / current_price - 1) * 100)
                        if item["target_price_high"] else None,
                })
            except Exception as e:
                logger.warning(f"관심종목 조회 실패: {item['ticker']} - {e}")

        return alerts
