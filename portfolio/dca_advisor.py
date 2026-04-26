"""DCA(정액 적립식) 어드바이저.

소수 종목(≤3) + S&P/NASDAQ 위주: 위험성향 기반 휴리스틱 비중.
다종목(≥4): HRP (기대수익률 추정 불필요, 적은 데이터에 강건).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from data.fetcher import StockDataFetcher
from portfolio.optimizer import PortfolioOptimizer
from utils.constants import (
    DCA_PRESET_2ASSET,
    SP500_TICKERS,
    NASDAQ100_TICKERS,
)
from utils.fx import get_usd_krw_rate


@dataclass
class DcaAllocation:
    ticker: str
    name: str
    market: str
    weight: float
    target_amount_krw: float
    price: float           # latest close (currency = native)
    currency: str
    shares: int
    spent_krw: float


@dataclass
class DcaPlan:
    monthly_amount: float          # KRW
    risk_level: str
    strategy: str                  # 'heuristic_2asset' | 'heuristic_blend' | 'hrp'
    allocations: list[DcaAllocation] = field(default_factory=list)
    leftover_krw: float = 0.0
    rationale: str = ""
    weights_json: str = ""

    def to_summary(self) -> dict:
        return {
            "monthly_amount": self.monthly_amount,
            "risk_level": self.risk_level,
            "strategy": self.strategy,
            "leftover_krw": self.leftover_krw,
            "rationale": self.rationale,
            "rows": [
                {
                    "ticker": a.ticker,
                    "name": a.name,
                    "market": a.market,
                    "weight": round(a.weight, 4),
                    "target_amount_krw": round(a.target_amount_krw, 0),
                    "price": a.price,
                    "currency": a.currency,
                    "shares": a.shares,
                    "spent_krw": round(a.spent_krw, 0),
                }
                for a in self.allocations
            ],
        }


class DcaAdvisor:
    def __init__(self):
        self.fetcher = StockDataFetcher()

    def recommend(
        self,
        tickers: list[dict],
        monthly_amount: float,
        risk_level: str = "중립",
        lookback: str = "2y",
    ) -> DcaPlan:
        """
        tickers: [{"ticker": "360750", "name": "TIGER 미국S&P500", "market": "KR"}, ...]
        monthly_amount: KRW
        """
        if not tickers:
            raise ValueError("tickers 비어있음")
        if monthly_amount <= 0:
            raise ValueError("monthly_amount > 0 필요")

        n = len(tickers)
        weights, strategy, rationale = self._decide_weights(tickers, risk_level, lookback)

        fx = get_usd_krw_rate()
        allocations = self._materialize(tickers, weights, monthly_amount, fx)
        spent = sum(a.spent_krw for a in allocations)
        leftover = max(0.0, monthly_amount - spent)

        return DcaPlan(
            monthly_amount=monthly_amount,
            risk_level=risk_level,
            strategy=strategy,
            allocations=allocations,
            leftover_krw=leftover,
            rationale=rationale,
            weights_json=json.dumps(weights, ensure_ascii=False),
        )

    # --- internal ---
    def _decide_weights(
        self, tickers: list[dict], risk_level: str, lookback: str
    ) -> tuple[dict[str, float], str, str]:
        n = len(tickers)
        sp_match = [t for t in tickers if t["ticker"].upper() in SP500_TICKERS]
        nq_match = [t for t in tickers if t["ticker"].upper() in NASDAQ100_TICKERS]

        # 1) S&P + NASDAQ 2종목만 있는 케이스
        if n == 2 and sp_match and nq_match:
            sp_w, nq_w = DCA_PRESET_2ASSET.get(
                risk_level, DCA_PRESET_2ASSET["중립"]
            )
            weights = {sp_match[0]["ticker"]: sp_w, nq_match[0]["ticker"]: nq_w}
            rationale = (
                f"S&P/NASDAQ 2종목 + 위험성향 '{risk_level}' → 휴리스틱 비중 "
                f"(S&P {sp_w*100:.0f}% / NASDAQ {nq_w*100:.0f}%). "
                "데이터가 적을 때 최적화 알고리즘은 노이즈에 취약하므로 룰베이스 사용."
            )
            return weights, "heuristic_2asset", rationale

        # 2) 종목 ≤ 3: 동일가중 + 위험성향에 따라 NASDAQ↑/SP↑ 미세 조정
        if n <= 3:
            base = 1.0 / n
            weights = {t["ticker"]: base for t in tickers}
            sp_w_pref, nq_w_pref = DCA_PRESET_2ASSET.get(
                risk_level, DCA_PRESET_2ASSET["중립"]
            )
            tilt = (nq_w_pref - sp_w_pref) * 0.2  # 최대 ±0.06
            for t in sp_match:
                weights[t["ticker"]] = max(0.05, weights[t["ticker"]] - tilt / max(1, len(sp_match)))
            for t in nq_match:
                weights[t["ticker"]] = weights[t["ticker"]] + tilt / max(1, len(nq_match))
            total = sum(weights.values())
            weights = {k: v / total for k, v in weights.items()}
            rationale = (
                f"{n}종목 동일가중 기반에서 위험성향 '{risk_level}'에 따라 "
                "NASDAQ/S&P 노출을 ±20% 범위 내 미세 조정."
            )
            return weights, "heuristic_blend", rationale

        # 3) 4종목 이상: HRP 사용
        prices = self.fetcher.get_multiple_prices(tickers, lookback)
        if prices.empty or len(prices.columns) < 2:
            base = 1.0 / n
            return (
                {t["ticker"]: base for t in tickers},
                "equal_weight",
                "가격 데이터 부족으로 동일가중 폴백.",
            )
        opt = PortfolioOptimizer(prices)
        result = opt.optimize_hrp()
        weights = {k: float(v) for k, v in result.weights.items() if v > 0.001}
        # 누락된 종목은 0으로 채움
        for t in tickers:
            weights.setdefault(t["ticker"], 0.0)
        rationale = (
            f"{n}종목 HRP(계층적 리스크 패리티) — 상관관계 군집 기반으로 "
            "리스크를 균등 배분. 기대수익률 추정 불필요."
        )
        return weights, "hrp", rationale

    def _materialize(
        self,
        tickers: list[dict],
        weights: dict[str, float],
        monthly_amount: float,
        fx: float,
    ) -> list[DcaAllocation]:
        # 종목별 최신 가격 1회씩만 조회
        rows: list[DcaAllocation] = []
        for t in tickers:
            w = weights.get(t["ticker"], 0.0)
            if w <= 0:
                continue
            target_krw = monthly_amount * w
            df = self.fetcher.get_price_data(t["ticker"], t.get("market", "US"), "1mo")
            if df.empty:
                rows.append(DcaAllocation(
                    ticker=t["ticker"], name=t.get("name", t["ticker"]),
                    market=t.get("market", "US"), weight=w,
                    target_amount_krw=target_krw, price=0.0,
                    currency="KRW" if t.get("market") == "KR" else "USD",
                    shares=0, spent_krw=0.0,
                ))
                continue
            close_col = "Close" if "Close" in df.columns else "종가"
            last_price = float(df[close_col].iloc[-1])
            currency = "KRW" if t.get("market") == "KR" else "USD"
            unit_price_krw = last_price if currency == "KRW" else last_price * fx
            shares = int(target_krw // unit_price_krw) if unit_price_krw > 0 else 0
            spent = shares * unit_price_krw
            rows.append(DcaAllocation(
                ticker=t["ticker"], name=t.get("name", t["ticker"]),
                market=t.get("market", "US"), weight=w,
                target_amount_krw=target_krw, price=last_price,
                currency=currency, shares=shares, spent_krw=spent,
            ))
        return rows
