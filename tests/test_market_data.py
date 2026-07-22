import numpy as np
import pandas as pd

from data.market_data import MarketDataProcessor


def _prices(n=60, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    data = {t: 100 * np.exp(rng.normal(0, 0.01, n).cumsum()) for t in ("AAA", "BBB")}
    return pd.DataFrame(data, index=idx)


def test_calculate_returns():
    mp = MarketDataProcessor()
    prices = _prices()
    rets = mp.calculate_returns(prices)
    assert len(rets) == len(prices) - 1  # 첫 행은 dropna
    # 수동 계산과 일치
    manual = prices["AAA"].iloc[1] / prices["AAA"].iloc[0] - 1
    assert abs(rets["AAA"].iloc[0] - manual) < 1e-9


def test_calculate_cumulative_returns():
    mp = MarketDataProcessor()
    prices = _prices()
    cum = mp.calculate_cumulative_returns(prices)
    # 첫 행은 0%
    assert abs(cum["AAA"].iloc[0]) < 1e-9
    last = (prices["AAA"].iloc[-1] / prices["AAA"].iloc[0] - 1) * 100
    assert abs(cum["AAA"].iloc[-1] - last) < 1e-6


def test_calculate_volatility_annualized():
    mp = MarketDataProcessor()
    prices = _prices()
    vol = mp.calculate_volatility(prices, window=20)
    tail = vol["AAA"].dropna()
    assert not tail.empty
    assert (tail >= 0).all()


def test_calculate_correlation():
    mp = MarketDataProcessor()
    prices = _prices()
    corr = mp.calculate_correlation(prices)
    assert corr.shape == (2, 2)
    assert abs(corr.loc["AAA", "AAA"] - 1.0) < 1e-9
    assert abs(corr.loc["AAA", "BBB"] - corr.loc["BBB", "AAA"]) < 1e-9
