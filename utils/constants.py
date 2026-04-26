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

# Korean stock/ETF ticker map
KR_STOCK_MAP = {
    "005930": "삼성전자", "000660": "SK하이닉스", "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스", "005380": "현대자동차", "000270": "기아",
    "068270": "셀트리온", "035420": "NAVER", "035720": "카카오",
    "051910": "LG화학", "006400": "삼성SDI", "105560": "KB금융",
    "055550": "신한지주", "066570": "LG전자", "028260": "삼성물산",
    "133690": "TIGER 미국나스닥100", "360750": "TIGER 미국S&P500",
    "381170": "TIGER 미국나스닥100커버드콜(합성)", "379800": "TIGER 미국S&P500TR(H)",
    "381180": "TIGER 미국테크TOP10 INDXX", "143850": "TIGER 미국S&P500선물(H)",
    "395160": "TIGER 미국배당+7%프리미엄다우존스", "458730": "TIGER 미국S&P500동일가중",
    "473460": "TIGER 미국나스닥100+15%프리미엄초단기",
    "069500": "KODEX 200", "229200": "KODEX 코스닥150",
    "305720": "KODEX 2차전지산업", "364690": "KODEX 나스닥100TR",
    "379810": "KODEX 미국S&P500TR", "461500": "KODEX 미국배당다우존스",
    "252670": "KODEX 200선물인버스2X", "122630": "KODEX 레버리지",
    "304660": "KODEX 미국채울트라30년선물(H)",
    "411060": "ACE 미국나스닥100", "360200": "ACE 미국S&P500",
}

# Portfolio optimization constants
DEFAULT_RISK_FREE_RATE = 0.04
BL_TAU = 0.05
INVESTABLE_SAVINGS_RATIO = 0.5

# ISA defaults (한국 ISA 일반형 기준)
ISA_ANNUAL_LIMIT = 24_000_000   # 연간 납입 한도
ISA_TAX_OPTIONS = ["general", "flexible", "reborn"]  # 일반형 / 중개형 / 서민형 등 분류 placeholder

# DCA risk-level → S&P : NASDAQ 비중 매핑 (보수적일수록 S&P 비중↑)
DCA_PRESET_2ASSET = {
    "매우 보수적": (0.70, 0.30),
    "보수적":     (0.60, 0.40),
    "중립":       (0.55, 0.45),
    "공격적":     (0.45, 0.55),
    "매우 공격적": (0.35, 0.65),
}

# Common S&P 500 / NASDAQ 100 ETF tickers (KR 상장 + US 상장)
SP500_TICKERS = {"VOO", "SPY", "IVV", "360750", "379800", "143850", "458730", "360200", "379810"}
NASDAQ100_TICKERS = {"QQQ", "QQQM", "133690", "364690", "411060", "381170", "381180", "473460"}

# Disclaimer
DISCLAIMER = (
    "본 정보는 투자 권유가 아니며, 투자 결정의 책임은 사용자에게 있습니다. "
    "투자에는 원금 손실 위험이 있습니다."
)
