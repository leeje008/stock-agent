import pandas as pd
from fredapi import Fred

from config import FRED_API_KEY
from utils.constants import FRED_INDICATORS
from utils.helpers import read_cache, write_cache


class EconomicDataFetcher:
    """미국 경제지표 수집기 (FRED API)"""

    def __init__(self):
        if not FRED_API_KEY:
            raise ValueError("FRED_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        self.fred = Fred(api_key=FRED_API_KEY)

    def get_indicator(self, series_id: str, period: str = "2y") -> pd.Series:
        cache_key = f"fred_{series_id}_{period}"
        cached = read_cache(cache_key)
        if cached is not None:
            return pd.Series(cached)

        data = self.fred.get_series(series_id)
        if period == "1y":
            data = data.last("365D")
        elif period == "2y":
            data = data.last("730D")

        write_cache(cache_key, data.to_dict())
        return data

    def get_macro_indicators(self) -> dict[str, pd.Series]:
        indicators = {}
        for name, series_id in FRED_INDICATORS.items():
            try:
                indicators[name] = self.get_indicator(series_id)
            except Exception as e:
                print(f"[WARN] {name} 수집 실패: {e}")
        return indicators

    def get_macro_summary(self) -> dict:
        summary = {}
        for name, series_id in FRED_INDICATORS.items():
            try:
                data = self.get_indicator(series_id)
                if not data.empty:
                    summary[name] = {
                        "latest": float(data.iloc[-1]),
                        "date": str(data.index[-1].date()),
                        "change_1m": float(data.iloc[-1] - data.iloc[-22])
                        if len(data) > 22
                        else None,
                    }
            except Exception:
                pass
        return summary
