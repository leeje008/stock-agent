import numpy as np
import pandas as pd

from analysis import risk


def _prices(n=250, seed=4):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    data = {}
    for i, tkr in enumerate(["AAA", "BBB", "CCC"]):
        rets = rng.normal(0.0003, 0.013 + i * 0.002, n)
        data[tkr] = 100 * np.exp(rets.cumsum())
    return pd.DataFrame(data, index=dates)


def test_var_cvar_positive_and_ordered():
    prices = _prices()
    w = {"AAA": 0.4, "BBB": 0.3, "CCC": 0.3}
    var = risk.portfolio_var(prices, w, alpha=0.95)
    cvar = risk.portfolio_cvar(prices, w, alpha=0.95)
    assert var >= 0.0 and cvar >= 0.0
    # CVaR(기대손실)는 VaR 이상이어야 한다
    assert cvar >= var - 1e-9


def test_correlation_matrix_shape():
    prices = _prices()
    corr = risk.correlation_matrix(prices)
    assert corr.shape == (3, 3)
    assert abs(corr.iloc[0, 0] - 1.0) < 1e-9


def test_concentration_alerts():
    alerts = risk.concentration_alerts({"AAA": 0.5, "BBB": 0.3, "CCC": 0.2}, threshold=0.30)
    assert len(alerts) == 1
    assert alerts[0]["ticker"] == "AAA"
    # 모든 종목이 임계 이하 → 경고 없음
    empty = risk.concentration_alerts(
        {"AAA": 0.25, "BBB": 0.25, "CCC": 0.25, "DDD": 0.25}, threshold=0.30
    )
    assert empty == []


def test_hhi_bounds():
    assert risk.herfindahl_index({}) == 0.0
    single = risk.herfindahl_index({"AAA": 1.0})
    assert abs(single - 1.0) < 1e-9
