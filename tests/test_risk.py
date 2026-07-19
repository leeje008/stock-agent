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


def test_parametric_and_mc_var_positive():
    prices = _prices()
    w = {"AAA": 0.4, "BBB": 0.3, "CCC": 0.3}
    pv = risk.parametric_var(prices, w, alpha=0.95)
    mv = risk.monte_carlo_var(prices, w, alpha=0.95, n_sims=5000)
    hv = risk.portfolio_var(prices, w, alpha=0.95)
    assert pv >= 0.0 and mv >= 0.0 and hv >= 0.0
    # 세 방식이 같은 규모(자릿수)여야 한다
    assert abs(pv - mv) < 0.02
    assert abs(pv - hv) < 0.03


def test_var_empty_data_zero():
    empty = __import__("pandas").DataFrame()
    assert risk.parametric_var(empty, {"AAA": 1.0}) == 0.0
    assert risk.monte_carlo_var(empty, {"AAA": 1.0}) == 0.0


def test_stress_scenarios():
    rows = risk.stress_scenarios(1_000_000, [-0.1, -0.2])
    assert len(rows) == 2
    assert rows[0]["loss_amount"] == 100_000.0
    assert rows[1]["loss_amount"] == 200_000.0
    # 기본 시나리오
    assert len(risk.stress_scenarios(1000)) == 4


def test_portfolio_beta():
    import numpy as np
    import pandas as pd
    prices = _prices()
    w = {"AAA": 0.4, "BBB": 0.3, "CCC": 0.3}
    pr = risk.portfolio_returns(prices, w)
    # 벤치마크 = 포트폴리오 자신 → 베타 ≈ 1
    beta_self = risk.portfolio_beta(prices, w, pr)
    assert abs(beta_self - 1.0) < 1e-6
    # 무관한 벤치마크(0 분산 아님) → 유한값
    rng = np.random.default_rng(7)
    bench = pd.Series(rng.normal(0, 0.01, len(pr)), index=pr.index)
    beta = risk.portfolio_beta(prices, w, bench)
    assert np.isfinite(beta)


def test_portfolio_beta_empty():
    import pandas as pd
    assert risk.portfolio_beta(_prices(), {"AAA": 1.0}, pd.Series(dtype=float)) == 0.0
