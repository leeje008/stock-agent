from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Holding:
    ticker: str
    market: str  # KR, US, ETF
    name: str
    quantity: int
    avg_price: float
    currency: str = "KRW"
    sector: str | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Transaction:
    ticker: str
    market: str
    action: str  # BUY, SELL
    quantity: int
    price: float
    currency: str = "KRW"
    note: str | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class OptimizationResult:
    strategy: str
    weights: dict[str, float] = field(default_factory=dict)
    expected_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0


@dataclass
class AnalysisReport:
    report_type: str
    content: str
    metadata: dict | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class PortfolioSnapshot:
    date: str
    total_value: float
    total_cost: float
    holdings_json: str | None = None
    id: int | None = None


@dataclass
class IsaAccount:
    """ISA 계좌 메타. 사용자는 보통 1개만 사용하지만 다중 계좌 대비."""
    account_name: str
    monthly_contribution: float  # 기본 월 적립금 (KRW)
    risk_level: str = "중립"     # 보수 / 중립 / 공격
    start_date: str | None = None
    annual_limit: float = 24_000_000  # 일반형 ISA 한도 (만 19세 이상)
    tax_status: str = "general"  # general | flexible | reborn
    note: str | None = None
    id: int | None = None
    created_at: str | None = None


@dataclass
class MonthlyContribution:
    """월별 실제 납입 기록. UNIQUE(account_id, year_month)."""
    account_id: int
    year_month: str  # 'YYYY-MM'
    amount: float
    note: str | None = None
    id: int | None = None
    created_at: str | None = None


@dataclass
class TargetAllocationHistory:
    """목표 비중 변경 이력. 월 적립금 변동 시 자동 스냅샷."""
    account_id: int
    set_date: str         # 'YYYY-MM-DD'
    weights_json: str     # {"VOO": 0.5, "QQQ": 0.5}
    monthly_amount: float
    strategy: str         # 'heuristic_balanced' | 'hrp' | 'manual' ...
    reason: str | None = None
    id: int | None = None
    created_at: str | None = None
