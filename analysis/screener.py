import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.helpers import read_cache, write_cache
from utils.logger import get_logger

logger = get_logger("screener")

# S&P 500 주요 종목 (대표 50개)
SP500_TOP = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "UNH", "JNJ", "V", "XOM", "JPM", "PG", "MA", "HD", "CVX", "MRK",
    "ABBV", "LLY", "PEP", "KO", "COST", "AVGO", "TMO", "WMT", "MCD",
    "CSCO", "ACN", "ABT", "DHR", "NEE", "LIN", "TXN", "PM", "UNP",
    "RTX", "LOW", "AMGN", "HON", "INTC", "IBM", "GE", "CAT", "BA",
    "SBUX", "GS", "BLK", "ISRG", "SYK",
]


def screen_kr_market(market: str = "KOSPI", filters: dict | None = None) -> pd.DataFrame:
    """pykrx로 한국 시장 전체 스크리닝 (1초 내 완료)"""
    cache_key = f"screener_kr_{market}_{datetime.now().strftime('%Y%m%d')}"
    cached = read_cache(cache_key)
    if cached is not None:
        df = pd.DataFrame(cached)
    else:
        from pykrx import stock as krx
        today = datetime.today()
        # 최근 영업일 탐색 (주말/공휴일 대비)
        for delta in range(5):
            date_str = (today - timedelta(days=delta)).strftime("%Y%m%d")
            try:
                df = krx.get_market_fundamental(date_str, market=market)
                if not df.empty:
                    break
            except Exception:
                continue
        else:
            return pd.DataFrame()

        # 종목명 추가
        try:
            names = krx.get_market_ticker_and_name(date_str, market=market)
            if isinstance(names, dict):
                df["종목명"] = df.index.map(lambda x: names.get(x, x))
            else:
                df["종목명"] = df.index
        except Exception:
            df["종목명"] = df.index

        df = df.reset_index()
        df = df.rename(columns={"티커": "ticker"}) if "티커" in df.columns else df.rename(columns={df.columns[0]: "ticker"})

        cache_data = df.to_dict()
        write_cache(cache_key, cache_data)

    if filters:
        if filters.get("per_max") and "PER" in df.columns:
            df = df[(df["PER"] > 0) & (df["PER"] <= filters["per_max"])]
        if filters.get("pbr_max") and "PBR" in df.columns:
            df = df[(df["PBR"] > 0) & (df["PBR"] <= filters["pbr_max"])]
        if filters.get("div_min") and "DIV" in df.columns:
            df = df[df["DIV"] >= filters["div_min"]]

    return df.head(100)


def screen_us_stocks(universe: list[str] | None = None, filters: dict | None = None) -> pd.DataFrame:
    """yfinance로 미국 종목 스크리닝 (ThreadPoolExecutor 사용)"""
    import yfinance as yf

    if universe is None:
        universe = SP500_TOP

    cache_key = f"screener_us_{datetime.now().strftime('%Y%m%d')}"
    cached = read_cache(cache_key)
    if cached is not None:
        results = cached
    else:
        results = []

        def _fetch_info(ticker):
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                return {
                    "ticker": ticker,
                    "종목명": info.get("shortName", ticker),
                    "PER": info.get("trailingPE"),
                    "PBR": info.get("priceToBook"),
                    "DIV": (info.get("dividendYield") or 0) * 100,
                    "ROE": (info.get("returnOnEquity") or 0) * 100,
                    "시가총액": info.get("marketCap", 0),
                    "현재가": info.get("currentPrice", 0),
                    "섹터": info.get("sector", ""),
                }
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_fetch_info, t) for t in universe]
            for f in as_completed(futures):
                r = f.result()
                if r:
                    results.append(r)

        write_cache(cache_key, results)

    df = pd.DataFrame(results)
    if df.empty:
        return df

    if filters:
        if filters.get("per_max") and "PER" in df.columns:
            df = df[df["PER"].notna() & (df["PER"] > 0) & (df["PER"] <= filters["per_max"])]
        if filters.get("pbr_max") and "PBR" in df.columns:
            df = df[df["PBR"].notna() & (df["PBR"] > 0) & (df["PBR"] <= filters["pbr_max"])]
        if filters.get("div_min") and "DIV" in df.columns:
            df = df[df["DIV"] >= filters["div_min"]]
        if filters.get("roe_min") and "ROE" in df.columns:
            df = df[df["ROE"] >= filters["roe_min"]]

    return df.head(100)
