"""Streamlit 캐시 경계.

Streamlit은 위젯 조작마다 스크립트 전체를 재실행하므로, 매 재실행마다 반복되는
시세 조회를 캐싱해 네트워크/연산 비용을 제거한다. 캐시 키가 되는 인자는 모두
해시 가능한 원시값(튜플/문자열)으로 받는다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from data.fetcher import StockDataFetcher

# 시세 캐시 TTL (초). 장중에도 과도하게 오래된 값을 쓰지 않도록 5분으로 둔다.
PRICE_CACHE_TTL = 300


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def get_multiple_prices_cached(
    tickers_key: tuple[tuple[str, str], ...], period: str, _fetcher=None
) -> pd.DataFrame:
    """여러 종목 종가 DataFrame (캐시).

    tickers_key: ((ticker, market), ...) 형태의 해시 가능한 튜플
    _fetcher: 주입된 StockDataFetcher (언더스코어라 캐시 키에서 제외)
    """
    tickers = [{"ticker": t, "market": m} for t, m in tickers_key]
    return (_fetcher or StockDataFetcher()).get_multiple_prices(tickers, period)


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def get_price_data_cached(
    ticker: str, market: str, period: str, _fetcher=None
) -> pd.DataFrame:
    """단일 종목 OHLCV DataFrame (캐시). _fetcher 는 캐시 키에서 제외된다."""
    return (_fetcher or StockDataFetcher()).get_price_data(ticker, market, period)


def tickers_to_key(holdings) -> tuple[tuple[str, str], ...]:
    """보유종목 리스트를 캐시 키용 튜플로 변환한다."""
    return tuple((h.ticker, h.market) for h in holdings)


def ticker_dicts_to_key(tickers: list[dict]) -> tuple[tuple[str, str], ...]:
    """[{"ticker","market"}, ...] 리스트를 캐시 키용 튜플로 변환한다."""
    return tuple((t["ticker"], t.get("market", "KR")) for t in tickers)


# 스크리너/시뮬레이션 결과 캐시 TTL (초). 장중 갱신 빈도가 낮아 시세보다 길게 둔다.
COMPUTE_CACHE_TTL = 600


@st.cache_data(ttl=COMPUTE_CACHE_TTL, show_spinner=False)
def screen_market_cached(
    market: str, filters_items: tuple[tuple[str, float], ...]
) -> pd.DataFrame:
    """시장 스크리닝 결과 (캐시). filters 는 해시 가능한 (키,값) 튜플로 받는다."""
    from analysis.screener import screen_kr_market, screen_us_stocks

    filters = dict(filters_items)
    if market in ("KOSPI", "KOSDAQ"):
        return screen_kr_market(market, filters)
    return screen_us_stocks(filters=filters)


@st.cache_data(ttl=COMPUTE_CACHE_TTL, show_spinner=False)
def simulate_cached(
    initial_value: float,
    monthly_contribution: float,
    expected_annual_return: float,
    annual_volatility: float,
    years: int,
    n_simulations: int,
    goal_amount: float | None,
) -> dict:
    """몬테카를로 시뮬레이션 (캐시). simulate 는 seed 고정이라 결정적이다."""
    from analysis.monte_carlo import simulate

    return simulate(
        initial_value=initial_value,
        monthly_contribution=monthly_contribution,
        expected_annual_return=expected_annual_return,
        annual_volatility=annual_volatility,
        years=years,
        n_simulations=n_simulations,
        goal_amount=goal_amount,
    )
