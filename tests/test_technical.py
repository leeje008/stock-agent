import numpy as np
import pandas as pd

from analysis.technical import TechnicalAnalyzer


def _series(n=120, seed=0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1, n).cumsum()
    close = pd.Series(100 + steps)
    high = close + rng.uniform(0, 2, n)
    low = close - rng.uniform(0, 2, n)
    volume = pd.Series(rng.uniform(1e5, 1e6, n))
    return high, low, close, volume


def test_stochastic():
    high, low, close, _ = _series()
    out = TechnicalAnalyzer.stochastic(high, low, close)
    assert set(out) == {"k", "d"}
    k = out["k"].dropna()
    assert not k.empty
    assert (k.between(-0.01, 100.01)).all()


def test_ichimoku():
    high, low, close, _ = _series()
    out = TechnicalAnalyzer.ichimoku(high, low, close)
    assert set(out) == {"tenkan", "kijun", "senkou_a", "senkou_b", "chikou"}
    assert out["tenkan"].dropna().shape[0] > 0


def test_obv():
    _, _, close, volume = _series()
    obv = TechnicalAnalyzer.obv(close, volume)
    assert len(obv) == len(close)
    assert np.isfinite(obv.iloc[-1])


def test_overbought_oversold_influence_verdict():
    ta = TechnicalAnalyzer
    # 과매수/과매도가 양/음 카운터에 동시 계상되어 상쇄되지 않아야 한다
    assert ta._is_bear("스토캐스틱 과매수") is True
    assert ta._is_bull("스토캐스틱 과매수") is False
    assert ta._is_bull("스토캐스틱 과매도") is True
    assert ta._is_bear("스토캐스틱 과매도") is False
    assert ta._is_bull("과매도") is True and ta._is_bear("과매도") is False
    assert ta._is_bear("과매수") is True and ta._is_bull("과매수") is False
    # 일반 매수/매도 신호도 정상 분류
    assert ta._is_bull("MACD 매수") is True and ta._is_bear("MACD 매수") is False
    assert ta._is_bear("MACD 매도") is True and ta._is_bull("MACD 매도") is False


def test_signal_summary_with_extras():
    high, low, close, volume = _series()
    out = TechnicalAnalyzer.get_signal_summary(close, high=high, low=low, volume=volume)
    assert "signal" in out
    assert "stochastic_k" in out
    assert "obv_trend" in out
    # 기존 시그니처 (close만) 도 동작해야 함
    base = TechnicalAnalyzer.get_signal_summary(close)
    assert "signal" in base
