from db.models import (
    AnalysisReport,
    Holding,
    IsaAccount,
    MonthlyContribution,
    OptimizationResult,
    PortfolioSnapshot,
    Transaction,
)


def test_holding_defaults():
    h = Holding(ticker="AAPL", market="US", name="Apple", quantity=10, avg_price=150.0)
    assert h.currency == "KRW"
    assert h.sector is None
    assert h.id is None


def test_transaction_defaults():
    t = Transaction(ticker="AAPL", market="US", action="BUY", quantity=5, price=100.0)
    assert t.currency == "KRW"
    assert t.note is None


def test_optimization_result_default_factory_isolated():
    a = OptimizationResult(strategy="max_sharpe")
    b = OptimizationResult(strategy="min_vol")
    a.weights["AAA"] = 1.0
    # default_factory 이므로 인스턴스 간 dict 공유되면 안 됨
    assert b.weights == {}
    assert a.expected_return == 0.0


def test_analysis_report_and_snapshot():
    r = AnalysisReport(report_type="market", content="x")
    assert r.metadata is None
    s = PortfolioSnapshot(date="2024-01-01", total_value=100.0, total_cost=90.0)
    assert s.holdings_json is None


def test_isa_account_defaults():
    acc = IsaAccount(account_name="ISA", monthly_contribution=500_000)
    assert acc.annual_limit == 24_000_000
    assert acc.tax_status == "general"
    assert acc.risk_level == "중립"


def test_monthly_contribution():
    c = MonthlyContribution(account_id=1, year_month="2026-01", amount=500_000)
    assert c.account_id == 1
    assert c.amount == 500_000
