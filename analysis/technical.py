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
    def stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3,
    ) -> dict:
        """Stochastic Oscillator (%K, %D). 과매수(>80)/과매도(<20) 판단"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        rng = (highest_high - lowest_low).replace(0, np.nan)
        percent_k = 100 * (close - lowest_low) / rng
        percent_d = percent_k.rolling(window=d_period).mean()
        return {"k": percent_k, "d": percent_d}

    @staticmethod
    def ichimoku(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        conversion: int = 9,
        base: int = 26,
        span_b: int = 52,
    ) -> dict:
        """일목균형표 (Ichimoku Cloud)"""
        def _mid(period: int) -> pd.Series:
            return (high.rolling(period).max() + low.rolling(period).min()) / 2

        tenkan = _mid(conversion)
        kijun = _mid(base)
        senkou_a = ((tenkan + kijun) / 2).shift(base)
        senkou_b = _mid(span_b).shift(base)
        chikou = close.shift(-base)
        return {
            "tenkan": tenkan,       # 전환선
            "kijun": kijun,         # 기준선
            "senkou_a": senkou_a,   # 선행스팬 A
            "senkou_b": senkou_b,   # 선행스팬 B
            "chikou": chikou,       # 후행스팬
        }

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """On-Balance Volume — 거래량 기반 매집/분산 추세"""
        direction = np.sign(close.diff().fillna(0))
        return (direction * volume).fillna(0).cumsum()

    @staticmethod
    def _is_bull(s: str) -> bool:
        """신호 문자열이 강세인지. "과매수"는 "매수"를 포함하므로 먼저 배제한다."""
        if "과매수" in s:
            return False
        return "과매도" in s or "매수" in s or "위" in s or "매집" in s

    @staticmethod
    def _is_bear(s: str) -> bool:
        """신호 문자열이 약세인지. "과매도"는 "매도"를 포함하므로 먼저 배제한다."""
        if "과매도" in s:
            return False
        return "과매수" in s or "매도" in s or "아래" in s or "돌파" in s or "분산" in s

    @staticmethod
    def get_signal_summary(
        prices: pd.Series,
        high: pd.Series | None = None,
        low: pd.Series | None = None,
        volume: pd.Series | None = None,
    ) -> dict:
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

        # Stochastic (고가/저가 제공 시)
        stoch_k = None
        if high is not None and low is not None and len(prices) >= 14:
            stoch = TechnicalAnalyzer.stochastic(high, low, prices)
            k_series = stoch["k"].dropna()
            if not k_series.empty:
                stoch_k = float(k_series.iloc[-1])
                if stoch_k > 80:
                    signals.append("스토캐스틱 과매수")
                elif stoch_k < 20:
                    signals.append("스토캐스틱 과매도")

        # OBV 추세 (거래량 제공 시)
        obv_trend = None
        if volume is not None and len(prices) >= 20:
            obv_series = TechnicalAnalyzer.obv(prices, volume)
            if len(obv_series) >= 6:
                recent = obv_series.iloc[-5:].mean()
                prev = obv_series.iloc[-10:-5].mean() if len(obv_series) >= 10 else obv_series.iloc[0]
                if recent > prev:
                    obv_trend = "상승"
                    signals.append("OBV 매집")
                else:
                    obv_trend = "하락"
                    signals.append("OBV 분산")

        # Determine overall signal (부분문자열 오탐 방지)
        bullish = sum(1 for s in signals if TechnicalAnalyzer._is_bull(s))
        bearish = sum(1 for s in signals if TechnicalAnalyzer._is_bear(s))

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
            "stochastic_k": round(stoch_k, 2) if stoch_k is not None else None,
            "obv_trend": obv_trend,
            "details": signals,
        }
