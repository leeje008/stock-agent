import pandas as pd
import numpy as np
from portfolio.optimizer import PortfolioOptimizer


class Backtester:
    """포트폴리오 최적화 전략 백테스팅"""

    def __init__(self, price_data: pd.DataFrame):
        """
        price_data: 각 종목의 일별 종가 DataFrame (columns=ticker, index=date)
        """
        self.prices = price_data

    def run_backtest(
        self,
        strategy: str = "max_sharpe",
        lookback_days: int = 252,
        rebalance_days: int = 63,
    ) -> dict:
        """Walk-forward 백테스트 실행

        strategy: "max_sharpe" | "min_volatility" | "equal_weight"
        lookback_days: 최적화에 사용할 과거 데이터 일수 (기본 1년)
        rebalance_days: 리밸런싱 주기 일수 (기본 분기)

        Returns: {
            "equity_curve": pd.Series (날짜별 포트폴리오 가치),
            "total_return": float,
            "annualized_return": float,
            "volatility": float,
            "sharpe_ratio": float,
            "max_drawdown": float,
            "strategy": str,
        }
        """
        prices = self.prices.copy()
        returns = prices.pct_change().dropna()

        # Start after the lookback period
        start_idx = lookback_days
        if start_idx >= len(returns):
            return {"error": "데이터가 부족합니다. 더 긴 기간의 데이터가 필요합니다."}

        portfolio_values = [1.0]  # Start with 1.0 (normalized)
        dates = [returns.index[start_idx]]

        current_weights = None
        days_since_rebalance = rebalance_days  # Force initial rebalance

        for i in range(start_idx, len(returns)):
            # Rebalance check
            if days_since_rebalance >= rebalance_days:
                lookback_prices = prices.iloc[i - lookback_days:i]
                try:
                    if strategy == "equal_weight":
                        n = len(prices.columns)
                        current_weights = {col: 1.0 / n for col in prices.columns}
                    else:
                        opt = PortfolioOptimizer(lookback_prices)
                        if strategy == "max_sharpe":
                            result = opt.optimize_max_sharpe()
                        elif strategy == "min_volatility":
                            result = opt.optimize_min_volatility()
                        elif strategy == "hrp":
                            result = opt.optimize_hrp()
                        elif strategy == "min_cvar":
                            result = opt.optimize_min_cvar()
                        else:
                            result = opt.optimize_max_sharpe()
                        current_weights = result.weights
                except Exception:
                    # If optimization fails, use equal weight
                    n = len(prices.columns)
                    current_weights = {col: 1.0 / n for col in prices.columns}
                days_since_rebalance = 0

            if current_weights is None:
                continue

            # Calculate daily portfolio return
            daily_return = sum(
                current_weights.get(col, 0) * returns.iloc[i][col]
                for col in prices.columns
            )

            new_value = portfolio_values[-1] * (1 + daily_return)
            portfolio_values.append(new_value)
            dates.append(returns.index[i])
            days_since_rebalance += 1

        equity = pd.Series(portfolio_values, index=dates)

        # Calculate metrics
        total_days = (equity.index[-1] - equity.index[0]).days
        total_return = equity.iloc[-1] / equity.iloc[0] - 1
        annualized_return = (1 + total_return) ** (365.0 / max(total_days, 1)) - 1

        daily_returns = equity.pct_change().dropna()
        vol = float(daily_returns.std() * np.sqrt(252))
        sharpe = float(annualized_return / vol) if vol > 0 else 0

        # Max drawdown
        rolling_max = equity.expanding().max()
        drawdowns = (equity - rolling_max) / rolling_max
        max_dd = float(drawdowns.min())

        return {
            "equity_curve": equity,
            "total_return": float(total_return),
            "annualized_return": float(annualized_return),
            "volatility": vol,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "strategy": strategy,
        }

    def compare_strategies(
        self,
        strategies: list[str] | None = None,
        lookback_days: int = 252,
        rebalance_days: int = 63,
    ) -> list[dict]:
        """여러 전략을 비교 백테스트

        Returns: list of backtest results per strategy
        """
        if strategies is None:
            strategies = ["max_sharpe", "min_volatility", "hrp", "min_cvar", "equal_weight"]

        results = []
        for strat in strategies:
            result = self.run_backtest(strat, lookback_days, rebalance_days)
            results.append(result)
        return results
