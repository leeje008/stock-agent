import pandas as pd

from portfolio.rebalancer import Rebalancer


def _portfolio_df():
    return pd.DataFrame([
        {"티커": "AAA", "평가금액(원)": 6_000_000},
        {"티커": "BBB", "평가금액(원)": 4_000_000},
    ])


def test_compute_current_weights():
    w = Rebalancer.compute_current_weights(_portfolio_df())
    assert abs(w["AAA"] - 0.6) < 1e-9
    assert abs(w["BBB"] - 0.4) < 1e-9


def test_compute_weights_empty():
    assert Rebalancer.compute_current_weights(pd.DataFrame()) == {}
    assert Rebalancer.compute_current_weights(None) == {}


def test_alerts_from_portfolio_no_targets(monkeypatch):
    rb = Rebalancer()
    # 목표 미설정 시 빈 리스트 (get_targets를 빈 dict로 모킹)
    monkeypatch.setattr(rb, "get_targets", lambda: {})
    assert rb.alerts_from_portfolio(_portfolio_df()) == []


def test_alerts_from_portfolio_with_targets(monkeypatch):
    rb = Rebalancer()
    monkeypatch.setattr(rb, "get_targets", lambda: {"AAA": 0.4, "BBB": 0.6})
    alerts = rb.alerts_from_portfolio(_portfolio_df(), threshold=0.05)
    tickers = {a["ticker"] for a in alerts}
    assert "AAA" in tickers and "BBB" in tickers
