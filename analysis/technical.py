import pandas as pd
import numpy as np


class TechnicalAnalyzer:
    """기술적 분석 지표 계산"""

    @staticmethod
    def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI (Relative Strength Index)"""
        delta = prices.diff()
        gain = delta.clip(lower=0).rolling(window=period).mean()
        loss = (-delta.clip(upper=0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """MACD (Moving Average Convergence Divergence)"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

    @staticmethod
    def bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
        """Bollinger Bands"""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return {"upper": upper, "middle": sma, "lower": lower}

    @staticmethod
    def moving_averages(prices: pd.Series) -> dict:
        """주요 이동평균선 (5, 20, 60, 120일)"""
        return {
            "MA5": prices.rolling(5).mean(),
            "MA20": prices.rolling(20).mean(),
            "MA60": prices.rolling(60).mean(),
            "MA120": prices.rolling(120).mean(),
        }

    @staticmethod
    def get_signal_summary(prices: pd.Series) -> dict:
        """종합 기술적 신호 요약"""
        if len(prices) < 30:
            return {"signal": "데이터 부족", "details": {}}

        current = float(prices.iloc[-1])
        rsi_val = float(TechnicalAnalyzer.rsi(prices).iloc[-1]) if len(prices) >= 14 else None
        macd_data = TechnicalAnalyzer.macd(prices)
        macd_val = float(macd_data["macd"].iloc[-1])
        signal_val = float(macd_data["signal"].iloc[-1])
        bb = TechnicalAnalyzer.bollinger_bands(prices)
        bb_upper = float(bb["upper"].iloc[-1])
        bb_lower = float(bb["lower"].iloc[-1])
        ma20 = float(prices.rolling(20).mean().iloc[-1])

        signals = []
        if rsi_val is not None:
            if rsi_val > 70:
                signals.append("과매수")
            elif rsi_val < 30:
                signals.append("과매도")
            else:
                signals.append("중립")

        if macd_val > signal_val:
            signals.append("MACD 매수")
        else:
            signals.append("MACD 매도")

        if current > bb_upper:
            signals.append("BB 상단 돌파")
        elif current < bb_lower:
            signals.append("BB 하단 돌파")

        if current > ma20:
            signals.append("20일선 위")
        else:
            signals.append("20일선 아래")

        # Determine overall signal
        bullish = sum(1 for s in signals if "매수" in s or "과매도" in s or "위" in s)
        bearish = sum(1 for s in signals if "매도" in s or "과매수" in s or "아래" in s or "돌파" in s)

        if bullish > bearish:
            overall = "매수 우위"
        elif bearish > bullish:
            overall = "매도 우위"
        else:
            overall = "중립"

        return {
            "signal": overall,
            "rsi": round(rsi_val, 2) if rsi_val else None,
            "macd": round(macd_val, 4),
            "macd_signal": round(signal_val, 4),
            "bb_position": "상단" if current > bb_upper else ("하단" if current < bb_lower else "중간"),
            "price_vs_ma20": "위" if current > ma20 else "아래",
            "details": signals,
        }
