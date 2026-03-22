import yfinance as yf

from utils.helpers import read_cache, write_cache

CACHE_KEY = "fx_usd_krw"
FALLBACK_RATE = 1350.0


def get_usd_krw_rate() -> float:
    cached = read_cache(CACHE_KEY)
    if cached is not None:
        return cached["rate"]

    try:
        ticker = yf.Ticker("KRW=X")
        rate = ticker.fast_info["lastPrice"]
        write_cache(CACHE_KEY, {"rate": rate})
        return float(rate)
    except Exception:
        return FALLBACK_RATE


def convert_to_krw(amount: float, currency: str) -> float:
    if currency == "KRW":
        return amount
    return amount * get_usd_krw_rate()


def convert_to_usd(amount: float, currency: str) -> float:
    if currency == "USD":
        return amount
    return amount / get_usd_krw_rate()
