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
        cost_bps: float = 0.0,
        rolling_window: int = 63,
    ) -> dict:
        """Walk-forward 백테스트 실행

        strategy: "max_sharpe" | "min_volatility" | "equal_weight"
        lookback_days: 최적화에 사용할 과거 데이터 일수 (기본 1년)
        rebalance_days: 리밸런싱 주기 일수 (기본 분기)
        cost_bps: 리밸런싱 회전율에 부과하는 거래비용 (bps, 0이면 비용 없음)
        rolling_window: 롤링 샤프/변동성 창 길이 (일)

        Returns 주요 키: equity_curve, total_return, annualized_return, volatility,
        sharpe_ratio, sortino_ratio, calmar_ratio, win_rate, max_drawdown,
        net_equity_curve, net_total_return, turnover, rolling_sharpe, rolling_vol.
        """
        prices = self.prices.copy()
        returns = prices.pct_change().dropna()

        # Start after the lookback period
        start_idx = lookback_days
        if start_idx >= len(returns):
            return {"error": "데이터가 부족합니다. 더 긴 기간의 데이터가 필요합니다."}

        portfolio_values = [1.0]  # gross (거래비용 미반영)
        net_values = [1.0]        # net (거래비용 반영)
        dates = [returns.index[start_idx]]

        current_weights = None
        prev_weights: dict[str, float] = {}
        total_turnover = 0.0
        days_since_rebalance = rebalance_days  # Force initial rebalance

        for i in range(start_idx, len(returns)):
            cost_today = 0.0
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

                # 회전율(turnover) = 직전 비중과의 절대차 합 (초기 편입 포함)
                cols = set(current_weights) | set(prev_weights)
                turnover_t = sum(
                    abs(current_weights.get(c, 0.0) - prev_weights.get(c, 0.0))
                    for c in cols
                )
                total_turnover += turnover_t
                cost_today = turnover_t * (cost_bps / 10000.0)
                prev_weights = dict(current_weights)
                days_since_rebalance = 0

            if current_weights is None:
                continue

            # Calculate daily portfolio return
            daily_return = sum(
                current_weights.get(col, 0) * returns.iloc[i][col]
                for col in prices.columns
            )

            portfolio_values.append(portfolio_values[-1] * (1 + daily_return))
            net_values.append(net_values[-1] * (1 + daily_return - cost_today))
            dates.append(returns.index[i])
            days_since_rebalance += 1

        equity = pd.Series(portfolio_values, index=dates)
        net_equity = pd.Series(net_values, index=dates)

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

        # Sortino ratio — 하방 변동성만 위험으로 간주
        downside = daily_returns[daily_returns < 0]
        downside_dev = float(downside.std() * np.sqrt(252)) if len(downside) > 1 else 0.0
        sortino = float(annualized_return / downside_dev) if downside_dev > 0 else 0.0

        # Calmar ratio — 연환산수익률 / 최대낙폭
        calmar = float(annualized_return / abs(max_dd)) if max_dd < 0 else 0.0

        # Win rate — 양(+) 일수익 비율
        win_rate = float((daily_returns > 0).mean()) if len(daily_returns) > 0 else 0.0

        # Rolling 지표 (연율화)
        rolling_vol = daily_returns.rolling(rolling_window).std() * np.sqrt(252)
        rolling_mean_ann = daily_returns.rolling(rolling_window).mean() * 252
        rolling_sharpe = rolling_mean_ann / rolling_vol.replace(0, np.nan)

        # Net (거래비용 반영) 성과
        net_total_return = net_equity.iloc[-1] / net_equity.iloc[0] - 1

        return {
            "equity_curve": equity,
            "total_return": float(total_return),
            "annualized_return": float(annualized_return),
            "volatility": vol,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "win_rate": win_rate,
            "max_drawdown": max_dd,
            "net_total_return": float(net_total_return),
            "turnover": float(total_turnover),
            "rolling_sharpe": rolling_sharpe,
            "rolling_vol": rolling_vol,
            "strategy": strategy,
        }

    def compare_strategies(
        self,
        strategies: list[str] | None = None,
        lookback_days: int = 252,
        rebalance_days: int = 63,
        cost_bps: float = 0.0,
    ) -> list[dict]:
        """여러 전략을 비교 백테스트

        cost_bps: 리밸런싱 회전율에 부과할 거래비용 (bps)
        Returns: list of backtest results per strategy
        """
        if strategies is None:
            strategies = ["max_sharpe", "min_volatility", "hrp", "min_cvar", "equal_weight"]

        results = []
        for strat in strategies:
            result = self.run_backtest(
                strat, lookback_days, rebalance_days, cost_bps=cost_bps
            )
            results.append(result)
        return results
