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
