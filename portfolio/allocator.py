from data.fetcher import StockDataFetcher
from portfolio.optimizer import PortfolioOptimizer
from db.models import OptimizationResult


class BudgetAllocator:
    """예산 배분 및 매수 가이드 생성"""

    def __init__(self):
        self.fetcher = StockDataFetcher()

    def generate_buy_guide(
        self,
        tickers: list[dict],
        budget: float,
        strategy: str = "max_sharpe",
        period: str = "1y",
    ) -> dict:
        """
        tickers: [{"ticker": "AAPL", "market": "US"}, ...]
        budget: 투자 가능 예산
        strategy: max_sharpe | min_volatility
        """
        prices = self.fetcher.get_multiple_prices(tickers, period)
        if prices.empty or len(prices.columns) < 2:
            return {"error": "최소 2개 이상의 종목 시세 데이터가 필요합니다."}

        optimizer = PortfolioOptimizer(prices)

        if strategy == "max_sharpe":
            result = optimizer.optimize_max_sharpe()
        elif strategy == "min_volatility":
            result = optimizer.optimize_min_volatility()
        else:
            result = optimizer.optimize_max_sharpe()

        active_weights = {k: v for k, v in result.weights.items() if v > 0.001}

        allocation = optimizer.calculate_discrete_allocation(active_weights, budget)

        return {
            "strategy": result.strategy,
            "optimal_weights": active_weights,
            "expected_return": result.expected_return,
            "volatility": result.volatility,
            "sharpe_ratio": result.sharpe_ratio,
            "buy_guide": allocation["allocation"],
            "invested": allocation["invested"],
            "leftover": allocation["leftover"],
        }
