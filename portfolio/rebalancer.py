from db.database import get_connection


class Rebalancer:
    """포트폴리오 리밸런싱 관리"""

    def save_targets(self, weights: dict[str, float], strategy: str):
        """최적화 결과를 목표 비중으로 저장"""
        conn = get_connection()
        conn.execute("DELETE FROM rebalancing_targets")
        for ticker, weight in weights.items():
            if weight > 0.001:
                conn.execute(
                    "INSERT OR REPLACE INTO rebalancing_targets (ticker, target_weight, strategy) VALUES (?, ?, ?)",
                    (ticker, weight, strategy),
                )
        conn.commit()
        conn.close()

    def get_targets(self) -> dict[str, float]:
        """저장된 목표 비중 조회"""
        conn = get_connection()
        rows = conn.execute("SELECT ticker, target_weight FROM rebalancing_targets").fetchall()
        conn.close()
        return {r["ticker"]: r["target_weight"] for r in rows}

    def get_target_strategy(self) -> str | None:
        """저장된 전략명 조회"""
        conn = get_connection()
        row = conn.execute("SELECT strategy FROM rebalancing_targets LIMIT 1").fetchone()
        conn.close()
        return row["strategy"] if row else None

    def check_drift(
        self, current_weights: dict[str, float], threshold: float = 0.05
    ) -> list[dict]:
        """현재 비중과 목표 비중의 드리프트 확인"""
        target_weights = self.get_targets()
        if not target_weights:
            return []

        alerts = []
        all_tickers = set(list(current_weights.keys()) + list(target_weights.keys()))

        for ticker in all_tickers:
            current = current_weights.get(ticker, 0)
            target = target_weights.get(ticker, 0)
            drift = current - target

            if abs(drift) > threshold:
                alerts.append({
                    "ticker": ticker,
                    "current": current,
                    "target": target,
                    "drift": drift,
                    "action": "매도" if drift > 0 else "매수",
                    "severity": "high" if abs(drift) > threshold * 2 else "medium",
                })

        return sorted(alerts, key=lambda x: abs(x["drift"]), reverse=True)

    def generate_rebalance_trades(
        self, drift_list: list[dict], total_value: float, prices: dict[str, float]
    ) -> list[dict]:
        """드리프트 해소를 위한 매매 수량 계산"""
        trades = []
        for item in drift_list:
            ticker = item["ticker"]
            trade_value = abs(item["drift"]) * total_value
            price = prices.get(ticker, 0)
            if price > 0:
                quantity = int(trade_value / price)
                if quantity > 0:
                    trades.append({
                        "ticker": ticker,
                        "action": item["action"],
                        "quantity": quantity,
                        "est_value": quantity * price,
                        "drift": item["drift"],
                    })
        return trades
