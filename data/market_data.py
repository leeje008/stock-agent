import yfinance as yf
import pandas as pd

from data.fetcher import StockDataFetcher


class MarketDataProcessor:
    """시세 데이터 가공 및 분석 유틸리티"""

    def __init__(self):
        self.fetcher = StockDataFetcher()

    def get_stock_info(self, ticker: str, market: str) -> dict:
        if market in ("US", "ETF"):
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                "name": info.get("shortName", ticker),
                "sector": info.get("sector", "N/A"),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", None),
                "dividend_yield": info.get("dividendYield", None),
                "52w_high": info.get("fiftyTwoWeekHigh", None),
                "52w_low": info.get("fiftyTwoWeekLow", None),
                "current_price": info.get("currentPrice", None),
            }
        return {"name": ticker, "sector": "N/A"}

    def calculate_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        return prices.pct_change().dropna()

    def calculate_cumulative_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        return (prices / prices.iloc[0] - 1) * 100

    def calculate_volatility(self, prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        returns = self.calculate_returns(prices)
        return returns.rolling(window=window).std() * (252 ** 0.5)

    def calculate_correlation(self, prices: pd.DataFrame) -> pd.DataFrame:
        returns = self.calculate_returns(prices)
        return returns.corr()
