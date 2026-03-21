import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, risk_models, expected_returns
from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices

from db.models import OptimizationResult


class PortfolioOptimizer:
    """포트폴리오 최적화 엔진 (Mean-Variance, Min Volatility)"""

    def __init__(self, price_data: pd.DataFrame):
        """
        price_data: 각 종목의 일별 종가 DataFrame
                    (columns=종목코드, index=날짜)
        """
        self.prices = price_data
        self.mu = expected_returns.mean_historical_return(price_data)
        self.cov = risk_models.sample_cov(price_data)

    def optimize_max_sharpe(self, risk_free_rate: float = 0.04) -> OptimizationResult:
        ef = EfficientFrontier(self.mu, self.cov)
        ef.max_sharpe(risk_free_rate=risk_free_rate)
        cleaned = ef.clean_weights()
        perf = ef.portfolio_performance(verbose=False, risk_free_rate=risk_free_rate)
        return OptimizationResult(
            strategy="max_sharpe",
            weights=dict(cleaned),
            expected_return=perf[0],
            volatility=perf[1],
            sharpe_ratio=perf[2],
        )

    def optimize_min_volatility(self) -> OptimizationResult:
        ef = EfficientFrontier(self.mu, self.cov)
        ef.min_volatility()
        cleaned = ef.clean_weights()
        perf = ef.portfolio_performance(verbose=False)
        return OptimizationResult(
            strategy="min_volatility",
            weights=dict(cleaned),
            expected_return=perf[0],
            volatility=perf[1],
            sharpe_ratio=perf[2],
        )

    def optimize_target_return(self, target_return: float) -> OptimizationResult:
        ef = EfficientFrontier(self.mu, self.cov)
        ef.efficient_return(target_return=target_return)
        cleaned = ef.clean_weights()
        perf = ef.portfolio_performance(verbose=False)
        return OptimizationResult(
            strategy=f"target_return_{target_return:.2f}",
            weights=dict(cleaned),
            expected_return=perf[0],
            volatility=perf[1],
            sharpe_ratio=perf[2],
        )

    def calculate_discrete_allocation(
        self, weights: dict[str, float], budget: float
    ) -> dict:
        latest_prices = get_latest_prices(self.prices)
        da = DiscreteAllocation(
            weights, latest_prices, total_portfolio_value=budget
        )
        allocation, leftover = da.greedy_portfolio()
        return {
            "allocation": allocation,
            "leftover": leftover,
            "invested": budget - leftover,
        }

    def get_efficient_frontier_data(self, n_points: int = 50) -> list[dict]:
        ef_data = []
        target_returns = np.linspace(
            self.mu.min(), self.mu.max(), n_points
        )
        for target in target_returns:
            try:
                ef = EfficientFrontier(self.mu, self.cov)
                ef.efficient_return(target_return=float(target))
                perf = ef.portfolio_performance(verbose=False)
                ef_data.append({
                    "return": perf[0],
                    "volatility": perf[1],
                    "sharpe": perf[2],
                })
            except Exception:
                continue
        return ef_data
