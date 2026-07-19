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


def test_backtest_rolling_and_turnover():
    bt = Backtester(_prices())
    res = bt.run_backtest("max_sharpe", lookback_days=120, rebalance_days=40, rolling_window=30)
    assert "error" not in res
    for key in ("rolling_sharpe", "rolling_vol", "turnover", "net_total_return"):
        assert key in res
    assert res["turnover"] >= 0.0
    # 롤링 지표는 Series
    assert hasattr(res["rolling_vol"], "index")
    # 창 길이 이후 유효값 존재
    assert res["rolling_vol"].dropna().shape[0] > 0


def test_backtest_cost_zero_equals_gross():
    bt = Backtester(_prices(seed=5))
    res = bt.run_backtest("equal_weight", lookback_days=120, rebalance_days=40, cost_bps=0.0)
    assert abs(res["net_total_return"] - res["total_return"]) < 1e-9


def test_backtest_cost_reduces_return():
    bt = Backtester(_prices(seed=5))
    res = bt.run_backtest("max_sharpe", lookback_days=120, rebalance_days=40, cost_bps=50.0)
    # 거래비용이 있으면 net <= gross
    assert res["net_total_return"] <= res["total_return"] + 1e-9


def test_backtest_equal_weight_edges():
    bt = Backtester(_prices(seed=2))
    res = bt.run_backtest("equal_weight", lookback_days=120, rebalance_days=60)
    assert "error" not in res
    assert res["calmar_ratio"] >= 0.0 or res["max_drawdown"] < 0
