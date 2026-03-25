import yfinance as yf
from pykrx import stock as krx
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from utils.helpers import read_cache, write_cache, retry
from utils.logger import get_logger

logger = get_logger("fetcher")


class StockDataFetcher:
    """한국/미국/글로벌 주식 데이터 통합 수집기"""

    def get_price_data(
        self, ticker: str, market: str, period: str = "1y"
    ) -> pd.DataFrame:
        cache_key = f"price_{market}_{ticker}_{period}"
        cached = read_cache(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        if market == "KR":
            df = self._fetch_krx(ticker, period)
            # pykrx 실패 시 yfinance fallback (.KS 접미사)
            if df.empty:
                df = self._fetch_yfinance(f"{ticker}.KS", period)
        else:
            df = self._fetch_yfinance(ticker, period)

        if not df.empty:
            logger.info(f"가격 데이터 수집: {market}/{ticker}, {len(df)}일치")
            cache_df = df.copy()
            cache_df.index = cache_df.index.astype(str)
            write_cache(cache_key, cache_df.to_dict())
        else:
            logger.warning(f"가격 데이터 없음: {market}/{ticker}")
        return df

    def get_multiple_prices(
        self, tickers: list[dict], period: str = "1y"
    ) -> pd.DataFrame:
        """여러 종목의 종가를 하나의 DataFrame으로 결합

        tickers: [{"ticker": "AAPL", "market": "US"}, {"ticker": "005930", "market": "KR"}, ...]
        Returns: DataFrame with columns=ticker names, index=dates
        """
        all_close = {}

        def _fetch_one(item):
            df = self.get_price_data(item["ticker"], item["market"], period)
            if not df.empty:
                close_col = "Close" if "Close" in df.columns else "종가"
                return item["ticker"], df[close_col]
            return item["ticker"], None

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_fetch_one, item) for item in tickers]
            for f in as_completed(futures):
                ticker, series = f.result()
                if series is not None:
                    all_close[ticker] = series

        combined = pd.DataFrame(all_close)
        combined = combined.ffill().dropna()
        return combined

    def get_financials(self, ticker: str, market: str) -> dict:
        if market == "US" or market == "ETF":
            stock = yf.Ticker(ticker)
            return {
                "income": stock.financials,
                "balance": stock.balance_sheet,
                "cashflow": stock.cashflow,
            }
        return {}

    def get_exchange_rate(self, pair: str = "KRW=X") -> float:
        ticker = yf.Ticker(pair)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return 1350.0  # fallback

    @retry(max_attempts=3, delay=1.0)
    def _fetch_yfinance(self, ticker: str, period: str) -> pd.DataFrame:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        return hist

    @retry(max_attempts=3, delay=1.0)
    def _fetch_krx(self, ticker: str, period: str) -> pd.DataFrame:
        period_days = {"6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
        days = period_days.get(period, 365)
        end = datetime.today()
        start = end - timedelta(days=days)
        df = krx.get_market_ohlcv(
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
            ticker,
        )
        return df
