import numpy as np
import pandas as pd

from analysis.backtest import Backtester


def _prices(n=400, seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    data = {}
    for i, tkr in enumerate(["AAA", "BBB", "CCC"]):
        rets = rng.normal(0.0004, 0.01 + i * 0.002, n)
        data[tkr] = 100 * np.exp(rets.cumsum())
    return pd.DataFrame(data, index=dates)


def test_backtest_new_metrics():
    bt = Backtester(_prices())
    res = bt.run_backtest("max_sharpe", lookback_days=120, rebalance_days=40)
    assert "error" not in res
    for key in ("sortino_ratio", "calmar_ratio", "win_rate"):
        assert key in res
        assert np.isfinite(res[key])
    assert 0.0 <= res["win_rate"] <= 1.0


def test_backtest_equal_weight_edges():
    bt = Backtester(_prices(seed=2))
    res = bt.run_backtest("equal_weight", lookback_days=120, rebalance_days=60)
    assert "error" not in res
    assert res["calmar_ratio"] >= 0.0 or res["max_drawdown"] < 0
