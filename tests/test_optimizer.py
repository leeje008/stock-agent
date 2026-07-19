import numpy as np
import pandas as pd

from portfolio.optimizer import PortfolioOptimizer


def _prices(n=300, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    data = {}
    for i, tkr in enumerate(["AAA", "BBB", "CCC", "DDD"]):
        rets = rng.normal(0.0005, 0.012 + i * 0.001, n)
        data[tkr] = 100 * np.exp(rets.cumsum())
    return pd.DataFrame(data, index=dates)


def test_sector_cap_respected():
    prices = _prices()
    opt = PortfolioOptimizer(prices)
    sector_map = {"AAA": "Tech", "BBB": "Tech", "CCC": "Fin", "DDD": "Fin"}
    sector_upper = {"Tech": 0.4}
    res = opt.optimize_max_sharpe(sector_map=sector_map, sector_upper=sector_upper)
    tech = res.weights.get("AAA", 0) + res.weights.get("BBB", 0)
    assert tech <= 0.4 + 1e-4


def test_weight_bounds_respected():
    prices = _prices()
    opt = PortfolioOptimizer(prices)
    res = opt.optimize_max_sharpe(weight_bounds=(0.1, 0.4))
    for w in res.weights.values():
        assert w <= 0.4 + 1e-4
        assert w >= 0.1 - 1e-4


def test_infeasible_weight_bounds_raises():
    # 2종목에 max 40% → 합이 1.0에 못 미쳐 실현 불가능 → 예외 (UI가 잡아 처리)
    import pytest
    prices = _prices()[["AAA", "BBB"]]
    opt = PortfolioOptimizer(prices)
    with pytest.raises(Exception):
        opt.optimize_max_sharpe(weight_bounds=(0.0, 0.4))


def test_weight_bounds_none_matches_default():
    prices = _prices()
    base = PortfolioOptimizer(prices).optimize_min_volatility()
    same = PortfolioOptimizer(prices).optimize_min_volatility(weight_bounds=None)
    for k in base.weights:
        assert abs(base.weights[k] - same.weights[k]) < 1e-6


def test_no_sector_map_matches_default():
    prices = _prices()
    base = PortfolioOptimizer(prices).optimize_max_sharpe()
    same = PortfolioOptimizer(prices).optimize_max_sharpe(sector_map=None, sector_upper=None)
    assert set(base.weights) == set(same.weights)
    for k in base.weights:
        assert abs(base.weights[k] - same.weights[k]) < 1e-6
