"""포트폴리오 리스크 분석 — VaR / CVaR / 상관관계 / 집중도 / 스트레스 / 베타.

과금 없는 순수 통계 계산만 사용한다 (numpy/pandas + stdlib).
"""
from statistics import NormalDist

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


def parametric_var(
    prices: pd.DataFrame, weights: dict[str, float], alpha: float = 0.95
) -> float:
    """정규분포 가정 파라메트릭 VaR. 손실 크기를 양수로 반환."""
    pr = portfolio_returns(prices, weights)
    if pr.empty or len(pr) < 2:
        return 0.0
    mu = float(pr.mean())
    sigma = float(pr.std(ddof=1))
    if sigma <= 0:
        return float(max(0.0, -mu))
    z = NormalDist().inv_cdf(1 - alpha)  # 예: alpha=0.95 -> -1.645
    quantile = mu + z * sigma
    return float(max(0.0, -quantile))


def monte_carlo_var(
    prices: pd.DataFrame,
    weights: dict[str, float],
    alpha: float = 0.95,
    n_sims: int = 10000,
    seed: int = 42,
) -> float:
    """몬테카를로 VaR (정규분포 파라미터 추정 후 시뮬레이션). 손실 크기 양수 반환."""
    pr = portfolio_returns(prices, weights)
    if pr.empty or len(pr) < 2:
        return 0.0
    mu = float(pr.mean())
    sigma = float(pr.std(ddof=1))
    if sigma <= 0:
        return float(max(0.0, -mu))
    rng = np.random.default_rng(seed)
    sims = rng.normal(mu, sigma, n_sims)
    quantile = np.percentile(sims, (1 - alpha) * 100)
    return float(max(0.0, -quantile))


def stress_scenarios(
    total_value: float, shocks: list[float] | None = None
) -> list[dict]:
    """시장충격 시나리오별 예상 손실 금액.

    shocks: 음수 수익률 리스트 (기본 -5%/-10%/-20%/-30%).
    Returns: [{"shock", "loss_pct", "loss_amount"}, ...]
    """
    if shocks is None:
        shocks = [-0.05, -0.10, -0.20, -0.30]
    rows = []
    for s in shocks:
        loss_pct = abs(s)
        rows.append({
            "shock": s,
            "loss_pct": loss_pct,
            "loss_amount": float(total_value * loss_pct),
        })
    return rows


def portfolio_beta(
    prices: pd.DataFrame,
    weights: dict[str, float],
    benchmark_returns: pd.Series,
) -> float:
    """벤치마크 대비 포트폴리오 베타 (cov(p, b) / var(b)).

    benchmark_returns: 벤치마크 일별 수익률 Series (index=날짜).
    공통 날짜만 정렬해 계산하며, 데이터 부족 시 0.0 반환.
    """
    pr = portfolio_returns(prices, weights)
    if pr.empty or benchmark_returns is None or benchmark_returns.empty:
        return 0.0
    joined = pd.concat([pr.rename("p"), benchmark_returns.rename("b")], axis=1).dropna()
    if len(joined) < 2:
        return 0.0
    var_b = float(joined["b"].var(ddof=1))
    if var_b <= 0:
        return 0.0
    cov_pb = float(joined["p"].cov(joined["b"]))
    return cov_pb / var_b
