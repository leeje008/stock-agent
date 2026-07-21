"""portfolio 핵심 모듈 단위테스트 (임시 SQLite 격리)."""
from db.models import Holding, IsaAccount, MonthlyContribution
from portfolio.isa_manager import IsaManager
from portfolio.manager import PortfolioManager
from portfolio.tracker import PortfolioTracker


def _holding(ticker="AAPL", market="US", name="Apple", qty=10, price=150.0,
             currency="USD", sector="Tech"):
    return Holding(ticker=ticker, market=market, name=name, quantity=qty,
                   avg_price=price, currency=currency, sector=sector)


# --- PortfolioManager ---

def test_add_and_get_holdings(temp_db):
    pm = PortfolioManager()
    pm.add_holding(_holding())
    pm.add_holding(_holding(ticker="005930", market="KR", name="삼성전자",
                            qty=5, price=70000.0, currency="KRW"))

    holdings = pm.get_all_holdings()
    assert len(holdings) == 2
    tickers = {h.ticker for h in holdings}
    assert tickers == {"AAPL", "005930"}


def test_get_holding_by_ticker(temp_db):
    pm = PortfolioManager()
    pm.add_holding(_holding())
    found = pm.get_holding_by_ticker("AAPL")
    assert found is not None
    assert found.quantity == 10
    assert pm.get_holding_by_ticker("NOPE") is None


def test_update_and_remove_holding(temp_db):
    pm = PortfolioManager()
    hid = pm.add_holding(_holding())
    pm.update_holding(hid, quantity=20, avg_price=160.0)
    updated = pm.get_holding_by_ticker("AAPL")
    assert updated.quantity == 20
    assert updated.avg_price == 160.0

    pm.remove_holding(hid)
    assert pm.get_all_holdings() == []


def test_update_or_merge_holding(temp_db):
    pm = PortfolioManager()
    hid = pm.add_holding(_holding(qty=10, price=100.0))
    pm.update_or_merge_holding(hid, quantity=15, avg_price=120.0)
    merged = pm.get_holding_by_ticker("AAPL")
    assert merged.quantity == 15
    assert merged.avg_price == 120.0


def test_portfolio_summary(temp_db):
    pm = PortfolioManager()
    pm.add_holding(_holding(qty=10, price=100.0))
    summary = pm.get_portfolio_summary()
    assert isinstance(summary, dict)
    assert summary.get("total_holdings", 0) >= 1


def test_record_transactions_batch_dedupes(temp_db):
    pm = PortfolioManager()
    rows = [{
        "date": "2026-01-15", "ticker": "AAPL", "name": "Apple", "action": "BUY",
        "quantity": 5, "price": 150.0, "amount": 750.0, "fee": 0.0, "tax": 0.0,
        "currency": "USD", "market": "US",
    }]
    inserted, skipped = pm.record_transactions_batch(rows)
    assert inserted == 1 and skipped == 0

    # 동일 거래 재삽입 시 중복 제외
    inserted2, skipped2 = pm.record_transactions_batch(rows)
    assert inserted2 == 0 and skipped2 == 1

    txns = pm.get_transactions(limit=100)
    assert len(txns) == 1
    assert txns[0]["ticker"] == "AAPL"


def test_upload_history(temp_db):
    pm = PortfolioManager()
    assert pm.get_last_upload_info() is None
    pm.record_upload_history("tx.csv", "범용 (직접입력)", 10, 8, 2)
    info = pm.get_last_upload_info()
    assert info is not None
    assert info["inserted_transactions"] == 8


# --- PortfolioTracker ---

def test_tracker_snapshot_and_history(temp_db):
    tracker = PortfolioTracker()
    tracker.take_snapshot(1_200_000, 1_000_000, [{"ticker": "AAPL", "value": 1_200_000}])

    history = tracker.get_history(days=30)
    assert len(history) == 1
    row = history[0]
    assert row["total_value"] == 1_200_000
    assert row["pnl"] == 200_000
    assert abs(row["return_pct"] - 20.0) < 1e-9

    latest = tracker.get_latest_snapshot()
    assert latest is not None
    assert latest["total_value"] == 1_200_000


def test_tracker_same_day_snapshot_replaces(temp_db):
    tracker = PortfolioTracker()
    tracker.take_snapshot(1_000_000, 900_000, [])
    tracker.take_snapshot(1_100_000, 900_000, [])
    history = tracker.get_history(days=30)
    # 같은 날짜는 REPLACE 되어 1건만 남는다
    assert len(history) == 1
    assert history[0]["total_value"] == 1_100_000


def test_tracker_empty_history(temp_db):
    assert PortfolioTracker().get_history(days=30) == []
    assert PortfolioTracker().get_latest_snapshot() is None


# --- IsaManager ---

def test_isa_account_upsert_and_get(temp_db):
    mgr = IsaManager()
    acc_id = mgr.upsert_account(IsaAccount(
        account_name="내 ISA", monthly_contribution=500_000, risk_level="중립",
    ))
    assert acc_id > 0
    acc = mgr.get_account(acc_id)
    assert acc is not None
    assert acc.account_name == "내 ISA"
    assert acc.monthly_contribution == 500_000


def test_isa_contribution_and_year_total(temp_db):
    mgr = IsaManager()
    acc_id = mgr.upsert_account(IsaAccount(
        account_name="내 ISA", monthly_contribution=500_000,
    ))
    mgr.record_contribution(MonthlyContribution(
        account_id=acc_id, year_month="2026-01", amount=500_000,
    ))
    mgr.record_contribution(MonthlyContribution(
        account_id=acc_id, year_month="2026-02", amount=700_000,
    ))

    contributions = mgr.get_contributions(acc_id)
    assert len(contributions) == 2
    assert mgr.get_year_total(acc_id, 2026) == 1_200_000
    # 다른 연도는 0
    assert mgr.get_year_total(acc_id, 2025) == 0


def test_isa_contribution_same_month_replaces(temp_db):
    mgr = IsaManager()
    acc_id = mgr.upsert_account(IsaAccount(
        account_name="내 ISA", monthly_contribution=500_000,
    ))
    mgr.record_contribution(MonthlyContribution(
        account_id=acc_id, year_month="2026-03", amount=300_000,
    ))
    mgr.record_contribution(MonthlyContribution(
        account_id=acc_id, year_month="2026-03", amount=800_000,
    ))
    assert mgr.get_year_total(acc_id, 2026) == 800_000
