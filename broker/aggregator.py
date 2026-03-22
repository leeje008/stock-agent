from collections import defaultdict


class TransactionAggregator:
    """거래 내역을 종합하여 현재 보유 현황으로 변환

    적립식 매수(DCA)를 고려한 가중 평균 매입가 계산
    """

    def aggregate(self, transactions: list[dict]) -> list[dict]:
        """거래 내역을 종목별로 집계하여 현재 보유 현황 생성

        Args:
            transactions: BrokerCSVParser.parse()의 반환값
                [{"date", "ticker", "name", "action", "quantity", "price", "amount", "fee", "tax"}, ...]

        Returns:
            [
                {
                    "ticker": "133690",
                    "name": "TIGER 미국나스닥100",
                    "quantity": 15,
                    "avg_price": 81000.0,
                    "total_cost": 1215000.0,
                    "total_fee": 0.0,
                    "total_tax": 0.0,
                    "first_buy_date": "2024-01-15",
                    "last_buy_date": "2024-03-15",
                    "buy_count": 3,
                    "transaction_history": [...],
                },
                ...
            ]
        """
        # Sort by date
        sorted_txns = sorted(transactions, key=lambda x: x["date"])

        # Aggregate by ticker
        holdings = defaultdict(lambda: {
            "ticker": "",
            "name": "",
            "quantity": 0,
            "total_cost": 0.0,
            "total_fee": 0.0,
            "total_tax": 0.0,
            "buy_dates": [],
            "buy_count": 0,
            "sell_count": 0,
            "transaction_history": [],
        })

        for txn in sorted_txns:
            ticker = txn["ticker"]
            h = holdings[ticker]
            h["ticker"] = ticker
            h["name"] = txn["name"] or h["name"]
            h["transaction_history"].append(txn)

            if txn["action"] == "BUY":
                # Weighted average cost calculation
                existing_cost = h["total_cost"]
                new_cost = txn["price"] * txn["quantity"]
                h["quantity"] += txn["quantity"]
                h["total_cost"] = existing_cost + new_cost
                h["total_fee"] += txn.get("fee", 0)
                h["total_tax"] += txn.get("tax", 0)
                h["buy_dates"].append(txn["date"])
                h["buy_count"] += 1

            elif txn["action"] == "SELL":
                # Reduce quantity, proportionally reduce cost
                if h["quantity"] > 0:
                    avg_cost_per_share = h["total_cost"] / h["quantity"]
                    sell_qty = min(txn["quantity"], h["quantity"])
                    h["quantity"] -= sell_qty
                    h["total_cost"] -= avg_cost_per_share * sell_qty
                    h["total_cost"] = max(0, h["total_cost"])
                h["total_fee"] += txn.get("fee", 0)
                h["total_tax"] += txn.get("tax", 0)
                h["sell_count"] += 1

        # Build result (only holdings with quantity > 0)
        result = []
        for ticker, h in holdings.items():
            if h["quantity"] <= 0:
                continue

            avg_price = h["total_cost"] / h["quantity"] if h["quantity"] > 0 else 0
            result.append({
                "ticker": h["ticker"],
                "name": h["name"],
                "quantity": h["quantity"],
                "avg_price": round(avg_price, 2),
                "total_cost": round(h["total_cost"], 2),
                "total_fee": round(h["total_fee"], 2),
                "total_tax": round(h["total_tax"], 2),
                "first_buy_date": h["buy_dates"][0] if h["buy_dates"] else "",
                "last_buy_date": h["buy_dates"][-1] if h["buy_dates"] else "",
                "buy_count": h["buy_count"],
                "sell_count": h["sell_count"],
                "transaction_history": h["transaction_history"],
            })

        return sorted(result, key=lambda x: x["total_cost"], reverse=True)

    def get_dca_summary(self, transactions: list[dict], ticker: str) -> dict:
        """특정 종목의 적립식 매수 요약

        Returns:
            {
                "ticker": "133690",
                "name": "TIGER 미국나스닥100",
                "total_invested": 1200000,
                "current_quantity": 15,
                "avg_price": 80000,
                "buy_history": [
                    {"date": "2024-01-15", "quantity": 5, "price": 78000},
                    {"date": "2024-02-15", "quantity": 5, "price": 80000},
                    {"date": "2024-03-15", "quantity": 5, "price": 82000},
                ],
                "price_range": {"min": 78000, "max": 82000},
                "monthly_avg_amount": 400000,
            }
        """
        ticker_txns = [t for t in transactions if t["ticker"] == ticker and t["action"] == "BUY"]
        if not ticker_txns:
            return {}

        total_invested = sum(t["price"] * t["quantity"] for t in ticker_txns)
        total_qty = sum(t["quantity"] for t in ticker_txns)
        prices = [t["price"] for t in ticker_txns]

        # Calculate monthly average
        if len(ticker_txns) >= 2:
            from datetime import datetime
            dates = [datetime.strptime(t["date"], "%Y-%m-%d") for t in ticker_txns]
            months_span = max(1, (dates[-1] - dates[0]).days / 30)
            monthly_avg = total_invested / months_span
        else:
            monthly_avg = total_invested

        return {
            "ticker": ticker,
            "name": ticker_txns[0].get("name", ""),
            "total_invested": round(total_invested, 2),
            "current_quantity": total_qty,
            "avg_price": round(total_invested / total_qty, 2) if total_qty > 0 else 0,
            "buy_history": [
                {"date": t["date"], "quantity": t["quantity"], "price": t["price"]}
                for t in ticker_txns
            ],
            "price_range": {"min": min(prices), "max": max(prices)},
            "monthly_avg_amount": round(monthly_avg, 2),
        }
