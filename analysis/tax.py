"""세금 계산 — 해외주식 양도소득세 / 배당소득세 / ISA 비과세 한도.

모든 값은 참고용 추정치이며 세무 자문이 아니다.
순수 계산만 수행하며 외부 API에 의존하지 않는다.
"""
from __future__ import annotations

# 해외주식 양도소득세: 연간 양도차익에서 기본공제 후 22%(지방소득세 포함)
CAPITAL_GAINS_DEDUCTION = 2_500_000
CAPITAL_GAINS_RATE = 0.22

# 배당소득세: 원천징수 15.4%(소득세 14% + 지방소득세 1.4%)
DIVIDEND_TAX_RATE = 0.154
# 금융소득종합과세 기준 (연 2,000만원 초과)
COMPREHENSIVE_TAXATION_THRESHOLD = 20_000_000

# ISA 비과세 한도 (일반형 200만원 / 서민형 400만원), 초과분 9.9% 분리과세
ISA_EXEMPT_GENERAL = 2_000_000
ISA_EXEMPT_REBORN = 4_000_000
ISA_SEPARATE_TAX_RATE = 0.099


def capital_gains_tax(
    realized_gain: float,
    deduction: float = CAPITAL_GAINS_DEDUCTION,
    rate: float = CAPITAL_GAINS_RATE,
) -> dict:
    """해외주식 양도소득세 추정.

    realized_gain: 연간 실현 양도차익(손실이면 음수)
    Returns: {"realized_gain", "deduction_used", "taxable", "tax"}
    손실이거나 공제 이하이면 과세표준·세액 모두 0.
    """
    gain = float(realized_gain)
    if gain <= 0:
        return {"realized_gain": gain, "deduction_used": 0.0, "taxable": 0.0, "tax": 0.0}
    deduction_used = min(gain, float(deduction))
    taxable = max(0.0, gain - deduction_used)
    return {
        "realized_gain": gain,
        "deduction_used": deduction_used,
        "taxable": taxable,
        "tax": taxable * float(rate),
    }


def dividend_tax(
    dividend_income: float,
    rate: float = DIVIDEND_TAX_RATE,
    threshold: float = COMPREHENSIVE_TAXATION_THRESHOLD,
) -> dict:
    """배당소득세 추정 + 금융소득종합과세 대상 여부.

    Returns: {"dividend_income", "tax", "comprehensive_taxation", "threshold"}
    """
    income = max(0.0, float(dividend_income))
    return {
        "dividend_income": income,
        "tax": income * float(rate),
        "comprehensive_taxation": income > float(threshold),
        "threshold": float(threshold),
    }


def isa_exempt_limit(account_type: str = "general") -> float:
    """ISA 계좌 유형별 비과세 한도 (서민형=reborn 400만원, 그 외 200만원)."""
    return ISA_EXEMPT_REBORN if account_type == "reborn" else ISA_EXEMPT_GENERAL


def isa_tax_benefit(
    profit: float,
    account_type: str = "general",
    rate: float = ISA_SEPARATE_TAX_RATE,
) -> dict:
    """ISA 계좌 순이익에 대한 비과세 한도 적용 및 초과분 분리과세 추정.

    Returns: {"profit", "exempt_limit", "exempt_amount", "taxable", "tax", "saved_vs_normal"}
    saved_vs_normal: 일반 계좌(15.4%) 대비 절세 추정액.
    """
    net = float(profit)
    limit = isa_exempt_limit(account_type)
    if net <= 0:
        return {
            "profit": net, "exempt_limit": limit, "exempt_amount": 0.0,
            "taxable": 0.0, "tax": 0.0, "saved_vs_normal": 0.0,
        }
    exempt_amount = min(net, limit)
    taxable = max(0.0, net - exempt_amount)
    tax = taxable * float(rate)
    normal_tax = net * DIVIDEND_TAX_RATE
    return {
        "profit": net,
        "exempt_limit": limit,
        "exempt_amount": exempt_amount,
        "taxable": taxable,
        "tax": tax,
        "saved_vs_normal": max(0.0, normal_tax - tax),
    }


def realized_pnl_from_transactions(transactions: list[dict]) -> list[dict]:
    """거래내역에서 이동평균 원가 기준 실현손익을 산출한다.

    broker/aggregator.TransactionAggregator 와 동일한 이동평균 방식:
    BUY는 수량·원가를 누적하고, SELL은 평균단가 기준으로 원가를 비례 차감한다.
    수수료/세금은 실현손익에서 차감한다.

    transactions: [{"date","ticker","name","action","quantity","price","fee","tax"}, ...]
    Returns: [{"date","ticker","name","quantity","proceeds","cost_basis","gain"}, ...]
    """
    if not transactions:
        return []

    positions: dict[str, dict] = {}
    realized: list[dict] = []

    for txn in sorted(transactions, key=lambda x: x.get("date", "")):
        ticker = txn.get("ticker")
        if not ticker:
            continue
        action = str(txn.get("action", "")).upper()
        qty = float(txn.get("quantity") or 0)
        price = float(txn.get("price") or 0)
        if qty <= 0:
            continue

        pos = positions.setdefault(ticker, {"quantity": 0.0, "total_cost": 0.0})

        if action == "BUY":
            pos["quantity"] += qty
            pos["total_cost"] += price * qty
        elif action == "SELL":
            if pos["quantity"] <= 0:
                continue
            sell_qty = min(qty, pos["quantity"])
            avg_cost = pos["total_cost"] / pos["quantity"]
            cost_basis = avg_cost * sell_qty
            fee = float(txn.get("fee") or 0)
            tax = float(txn.get("tax") or 0)
            proceeds = price * sell_qty - fee - tax
            pos["quantity"] -= sell_qty
            pos["total_cost"] = max(0.0, pos["total_cost"] - cost_basis)
            realized.append({
                "date": txn.get("date", ""),
                "ticker": ticker,
                "name": txn.get("name", ticker),
                "quantity": sell_qty,
                "proceeds": proceeds,
                "cost_basis": cost_basis,
                "gain": proceeds - cost_basis,
            })

    return realized


def total_realized_gain(realized: list[dict]) -> float:
    """실현손익 합계 (손실 포함)."""
    return float(sum(r.get("gain", 0.0) for r in realized))
