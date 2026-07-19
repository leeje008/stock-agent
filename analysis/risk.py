"""포트폴리오 리스크 분석 — VaR / CVaR / 상관관계 / 집중도.

과금 없는 순수 통계 계산만 사용한다 (numpy/pandas).
"""
import numpy as np
import pandas as pd


def portfolio_returns(prices: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """가중 포트폴리오 일별 수익률 Series 반환"""
    if prices.empty or not weights:
        return pd.Series(dtype=float)
    cols = [c for c in prices.columns if c in weights and weights[c] != 0]
    if not cols:
        return pd.Series(dtype=float)
    rets = prices[cols].pct_change().dropna()
    w = np.array([weights[c] for c in cols], dtype=float)
    total = w.sum()
    if total > 0:
        w = w / total
    return rets.mul(w, axis=1).sum(axis=1)


def portfolio_var(
    prices: pd.DataFrame, weights: dict[str, float], alpha: float = 0.95
) -> float:
    """히스토리컬 Value at Risk. 손실 크기를 양수로 반환 (예: 0.023 = 2.3%)."""
    pr = portfolio_returns(prices, weights)
    if pr.empty:
        return 0.0
    q = np.percentile(pr, (1 - alpha) * 100)
    return float(max(0.0, -q))


def portfolio_cvar(
    prices: pd.DataFrame, weights: dict[str, float], alpha: float = 0.95
) -> float:
    """히스토리컬 Conditional VaR (기대손실). 손실 크기를 양수로 반환."""
    pr = portfolio_returns(prices, weights)
    if pr.empty:
        return 0.0
    q = np.percentile(pr, (1 - alpha) * 100)
    tail = pr[pr <= q]
    if tail.empty:
        return float(max(0.0, -q))
    return float(max(0.0, -tail.mean()))


def correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """보유 종목 일별 수익률 상관계수 행렬"""
    if prices.empty or prices.shape[1] < 1:
        return pd.DataFrame()
    return prices.pct_change().dropna(how="all").corr()


def concentration_alerts(
    weights: dict[str, float], threshold: float = 0.30
) -> list[dict]:
    """단일 종목 비중이 임계치를 초과하면 경고 리스트 반환"""
    if not weights:
        return []
    total = sum(abs(w) for w in weights.values())
    if total <= 0:
        return []
    alerts = []
    for ticker, w in weights.items():
        share = abs(w) / total
        if share > threshold:
            alerts.append({
                "ticker": ticker,
                "weight": round(share, 4),
                "threshold": threshold,
                "severity": "high" if share > threshold * 1.5 else "medium",
                "message": f"{ticker} 비중 {share * 100:.1f}% (임계 {threshold * 100:.0f}% 초과)",
            })
    return sorted(alerts, key=lambda x: x["weight"], reverse=True)


def herfindahl_index(weights: dict[str, float]) -> float:
    """허핀달-허쉬만 지수 (HHI) — 집중도 요약 (0~1, 클수록 집중)"""
    if not weights:
        return 0.0
    total = sum(abs(w) for w in weights.values())
    if total <= 0:
        return 0.0
    shares = [abs(w) / total for w in weights.values()]
    return float(sum(s * s for s in shares))
