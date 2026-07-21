"""캐시 계층 회귀 테스트 — 동일 입력에 동일 결과를 반환하고 재호출을 줄이는지."""
import numpy as np
import pandas as pd
import pytest
import streamlit as st

from ui.data_cache import (
    get_multiple_prices_cached,
    get_price_data_cached,
    tickers_to_key,
)


class _Holding:
    def __init__(self, ticker, market):
        self.ticker = ticker
        self.market = market


def _frame(seed=0, n=50):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = pd.Series(100 * np.exp(rng.normal(0, 0.01, n).cumsum()), index=idx)
    return pd.DataFrame({"Close": close, "High": close * 1.01, "Low": close * 0.99}, index=idx)


@pytest.fixture(autouse=True)
def _clear_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def test_tickers_to_key():
    holdings = [_Holding("AAPL", "US"), _Holding("005930", "KR")]
    assert tickers_to_key(holdings) == (("AAPL", "US"), ("005930", "KR"))


def test_price_cache_returns_same_result_and_hits_cache(monkeypatch):
    from data.fetcher import StockDataFetcher
    calls = {"n": 0}

    def fake(self, ticker, market, period="1y"):
        calls["n"] += 1
        return _frame(seed=1)

    monkeypatch.setattr(StockDataFetcher, "get_price_data", fake)

    first = get_price_data_cached("AAPL", "US", "1y")
    second = get_price_data_cached("AAPL", "US", "1y")
    # 동일 결과
    pd.testing.assert_frame_equal(first, second)
    # 두 번째는 캐시 히트 → 원본 호출은 1회
    assert calls["n"] == 1

    # 인자가 다르면 다시 조회
    get_price_data_cached("AAPL", "US", "6mo")
    assert calls["n"] == 2


def test_multi_price_cache_returns_same_result(monkeypatch):
    from data.fetcher import StockDataFetcher
    calls = {"n": 0}

    def fake_multi(self, tickers, period="1y"):
        calls["n"] += 1
        return pd.DataFrame({t["ticker"]: _frame(seed=i)["Close"] for i, t in enumerate(tickers)})

    monkeypatch.setattr(StockDataFetcher, "get_multiple_prices", fake_multi)

    key = (("AAA", "US"), ("BBB", "US"))
    first = get_multiple_prices_cached(key, "1y")
    second = get_multiple_prices_cached(key, "1y")
    pd.testing.assert_frame_equal(first, second)
    assert calls["n"] == 1


def test_portfolio_frame_cache_preserves_values(monkeypatch):
    """ui.context 의 캐시된 평가 프레임이 캐시 없이 계산한 값과 동일한지."""
    import ui.context as ctxmod

    monkeypatch.setattr(ctxmod, "get_usd_krw_rate", lambda: 1300.0)

    class _H:
        def __init__(self):
            self.id, self.ticker, self.market = 1, "AAA", "US"
            self.quantity, self.avg_price, self.currency = 10, 100.0, "USD"
            self.name, self.sector = "Alpha", "Tech"

    class _F:
        def get_price_data(self, ticker, market, period="5d"):
            return _frame(seed=2)

    holdings = [_H()]
    key = tuple((h.id, h.ticker, h.market, h.quantity, h.avg_price, h.currency) for h in holdings)
    df1 = ctxmod._build_portfolio_frame(key, holdings, _F())
    df2 = ctxmod._build_portfolio_frame(key, holdings, _F())
    pd.testing.assert_frame_equal(df1, df2)

    expected_price = float(_frame(seed=2)["Close"].iloc[-1])
    assert abs(float(df1["현재가"].iloc[0]) - expected_price) < 1e-9
    assert abs(float(df1["평가금액(원)"].iloc[0]) - expected_price * 10 * 1300.0) < 1e-6
    assert abs(float(df1["매입금액(원)"].iloc[0]) - 100.0 * 10 * 1300.0) < 1e-6
