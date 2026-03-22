import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, risk_models, expected_returns, BlackLittermanModel
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

    def optimize_black_litterman(
        self,
        views: dict[str, float],
        confidence: dict[str, float] | None = None,
        risk_free_rate: float = 0.04,
    ) -> OptimizationResult:
        """
        Black-Litterman 모델을 사용한 포트폴리오 최적화.

        views: 종목별 예상 수익률 (ticker -> expected return)
        confidence: 종목별 확신도 0~1 (ticker -> confidence)
        risk_free_rate: 무위험 수익률
        """
        # Filter views to only include tickers in our price data
        valid_views = {k: v for k, v in views.items() if k in self.prices.columns}
        if not valid_views:
            return self.optimize_max_sharpe(risk_free_rate)

        # Build picking matrix and view vector
        tickers = list(self.prices.columns)
        P = np.zeros((len(valid_views), len(tickers)))
        Q = np.zeros(len(valid_views))

        for i, (ticker, view) in enumerate(valid_views.items()):
            P[i, tickers.index(ticker)] = 1
            Q[i] = view

        # Confidence -> omega (uncertainty matrix)
        if confidence:
            tau = 0.05
            omega_diag = []
            for ticker in valid_views:
                conf = confidence.get(ticker, 0.5)
                # Lower confidence -> higher uncertainty
                omega_diag.append(tau * (1 - conf + 0.01))
            omega = np.diag(omega_diag)
        else:
            omega = None

        bl = BlackLittermanModel(
            self.cov,
            pi="market",
            Q=Q,
            P=P,
            omega=omega,
        )
        bl_returns = bl.bl_returns()

        ef = EfficientFrontier(bl_returns, self.cov)
        ef.max_sharpe(risk_free_rate=risk_free_rate)
        cleaned = ef.clean_weights()
        perf = ef.portfolio_performance(verbose=False, risk_free_rate=risk_free_rate)

        return OptimizationResult(
            strategy="black_litterman",
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
