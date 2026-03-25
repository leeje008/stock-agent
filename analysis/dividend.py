import yfinance as yf
from datetime import datetime

from utils.helpers import read_cache, write_cache
from utils.logger import get_logger

logger = get_logger("dividend")


def get_dividend_info(ticker: str, market: str, quantity: int, currency: str = "KRW") -> dict:
    """종목별 배당 정보 조회"""
    cache_key = f"dividend_{market}_{ticker}"
    cached = read_cache(cache_key)
    if cached is not None:
        cached["annual_income"] = (cached.get("annual_rate") or 0) * quantity
        return cached

    yf_ticker = f"{ticker}.KS" if market == "KR" else ticker
    try:
        stock = yf.Ticker(yf_ticker)
        info = stock.info

        dividend_yield = info.get("dividendYield") or 0
        dividend_rate = info.get("dividendRate") or 0
        payout_ratio = info.get("payoutRatio") or 0
        ex_date_ts = info.get("exDividendDate")
        ex_date = datetime.fromtimestamp(ex_date_ts).strftime("%Y-%m-%d") if ex_date_ts else None

        # 배당 성장률
        growth_rate = None
        try:
            divs = stock.dividends
            if len(divs) >= 8:
                yearly = divs.resample("YE").sum()
                if len(yearly) >= 2 and yearly.iloc[-2] > 0:
                    growth_rate = float(yearly.iloc[-1] / yearly.iloc[-2] - 1)
        except Exception:
            pass

        result = {
            "ticker": ticker,
            "yield": dividend_yield,
            "annual_rate": dividend_rate,
            "payout_ratio": payout_ratio,
            "ex_dividend_date": ex_date,
            "growth_rate": growth_rate,
            "annual_income": dividend_rate * quantity,
            "currency": currency,
        }

        write_cache(cache_key, result)
        return result

    except Exception as e:
        logger.warning(f"배당 정보 조회 실패: {ticker} - {e}")
        return {
            "ticker": ticker,
            "yield": 0,
            "annual_rate": 0,
            "payout_ratio": 0,
            "ex_dividend_date": None,
            "growth_rate": None,
            "annual_income": 0,
            "currency": currency,
        }


def get_portfolio_dividend_summary(holdings: list) -> dict:
    """전체 포트폴리오 배당 요약"""
    total_income_krw = 0
    dividend_data = []

    for h in holdings:
        info = get_dividend_info(h.ticker, h.market, h.quantity, h.currency)
        annual_income = info["annual_income"]

        # USD → KRW 변환 (대략)
        if h.currency == "USD":
            annual_income_krw = annual_income * 1350
        else:
            annual_income_krw = annual_income

        total_income_krw += annual_income_krw

        dividend_data.append({
            "ticker": h.ticker,
            "name": h.name,
            "quantity": h.quantity,
            "dividend_yield": info["yield"],
            "annual_rate": info["annual_rate"],
            "annual_income": annual_income,
            "annual_income_krw": annual_income_krw,
            "ex_dividend_date": info["ex_dividend_date"],
            "growth_rate": info["growth_rate"],
            "currency": h.currency,
        })

    return {
        "total_annual_income_krw": total_income_krw,
        "holdings": dividend_data,
    }
