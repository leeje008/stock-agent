"""앱 전체 헤드리스 스모크 (Streamlit AppTest).

네트워크/LLM 없이 결정적으로 실행하기 위해 데이터 페처와 보유종목을 모킹한다.
신규 리스크 탭 및 기술적 지표 렌더 경로가 예외 없이 실행되는지 확인한다.
"""
import numpy as np
import pandas as pd
import pytest

from db.models import Holding


def _fake_holdings():
    return [
        Holding(id=1, ticker="AAPL", market="US", name="Apple", quantity=10,
                avg_price=150.0, currency="USD", sector="Tech"),
        Holding(id=2, ticker="MSFT", market="US", name="Microsoft", quantity=5,
                avg_price=300.0, currency="USD", sector="Tech"),
        Holding(id=3, ticker="JPM", market="US", name="JPMorgan", quantity=8,
                avg_price=140.0, currency="USD", sector="Financial"),
    ]


def _ohlcv(seed=0, n=300):
    rng = np.random.default_rng(seed)
    close = pd.Series(100 * np.exp(rng.normal(0.0004, 0.012, n).cumsum()))
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    close.index = idx
    return pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.02,
        "Low": close * 0.98,
        "Close": close,
        "Volume": pd.Series(rng.uniform(1e5, 1e6, n), index=idx),
    }, index=idx)


def _multi(tickers, seed=1):
    cols = {}
    for i, item in enumerate(tickers):
        cols[item["ticker"]] = _ohlcv(seed=seed + i)["Close"]
    return pd.DataFrame(cols).ffill().dropna()


@pytest.fixture
def patched(monkeypatch):
    from portfolio.manager import PortfolioManager
    from data.fetcher import StockDataFetcher
    import utils.fx as fx

    monkeypatch.setattr(PortfolioManager, "get_all_holdings", lambda self: _fake_holdings())
    monkeypatch.setattr(StockDataFetcher, "get_price_data",
                        lambda self, ticker, market, period="1y": _ohlcv(seed=hash(ticker) % 7))
    monkeypatch.setattr(StockDataFetcher, "get_multiple_prices",
                        lambda self, tickers, period="1y": _multi(tickers))
    monkeypatch.setattr(fx, "get_usd_krw_rate", lambda: 1350.0)
    # context 모듈은 fx 심볼을 직접 import 하므로 그쪽도 패치
    import ui.context as ctxmod
    monkeypatch.setattr(ctxmod, "get_usd_krw_rate", lambda: 1350.0)
    yield


def test_app_runs_with_holdings(patched):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=90)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    # 리스크 관리 탭 라벨 존재 확인
    labels = []
    for t in at.tabs:
        lbl = getattr(t, "label", None)
        if lbl:
            labels.append(lbl)
    assert any("리스크 관리" == la for la in labels)
