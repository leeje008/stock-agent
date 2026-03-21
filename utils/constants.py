# Market identifiers
MARKET_KR = "KR"
MARKET_US = "US"
MARKET_ETF = "ETF"

# Risk levels
RISK_LEVELS = {
    "매우 보수적": 0.05,
    "보수적": 0.10,
    "중립": 0.15,
    "공격적": 0.20,
    "매우 공격적": 0.30,
}

# FRED economic indicator series IDs
FRED_INDICATORS = {
    "미국 기준금리": "FEDFUNDS",
    "미국 CPI": "CPIAUCSL",
    "미국 실업률": "UNRATE",
    "VIX (변동성지수)": "VIXCLS",
    "10년물 국채금리": "DGS10",
    "달러인덱스": "DTWEXBGS",
}

# Currency tickers for exchange rate
FX_TICKER_USDKRW = "KRW=X"

# Disclaimer
DISCLAIMER = (
    "본 정보는 투자 권유가 아니며, 투자 결정의 책임은 사용자에게 있습니다. "
    "투자에는 원금 손실 위험이 있습니다."
)
