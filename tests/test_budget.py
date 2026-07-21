"""budget 모듈 단위테스트 (임시 SQLite 격리)."""
from budget.analyzer import BudgetAnalyzer
from budget.manager import BudgetManager
from budget.models import BudgetEntry
from budget.recurring import RecurringExpenseManager


def _entry(date, amount, etype, category, description=None, recurring=0, day=None):
    return BudgetEntry(
        date=date, amount=amount, type=etype, category=category,
        description=description, is_recurring=recurring, recurring_day=day,
    )


def test_add_and_get_entries(temp_db):
    mgr = BudgetManager()
    mgr.add_entry(_entry("2026-05-03", 3_000_000, "income", "급여"))
    mgr.add_entry(_entry("2026-05-10", 50_000, "expense", "식비"))

    all_entries = mgr.get_entries(year_month="2026-05")
    assert len(all_entries) == 2

    incomes = mgr.get_entries(year_month="2026-05", entry_type="income")
    assert len(incomes) == 1
    assert incomes[0].amount == 3_000_000

    by_cat = mgr.get_entries(year_month="2026-05", category="식비")
    assert len(by_cat) == 1


def test_delete_entry(temp_db):
    mgr = BudgetManager()
    eid = mgr.add_entry(_entry("2026-05-11", 20_000, "expense", "카페/음료"))
    assert len(mgr.get_entries(year_month="2026-05")) == 1
    mgr.delete_entry(eid)
    assert mgr.get_entries(year_month="2026-05") == []


def test_add_entries_batch(temp_db):
    mgr = BudgetManager()
    rows = [
        {"date": "2026-06-01", "amount": 10_000, "type": "expense",
         "category": "식비", "description": "점심", "source": "csv"},
        {"date": "2026-06-02", "amount": 20_000, "type": "expense",
         "category": "교통", "description": "택시", "source": "csv"},
    ]
    inserted = mgr.add_entries_batch(rows)
    assert inserted == 2
    assert len(mgr.get_entries(year_month="2026-06")) == 2


def test_default_categories_seeded(temp_db):
    mgr = BudgetManager()
    cats = mgr.get_categories()
    assert len(cats) > 0
    names = {c.name for c in cats}
    assert "식비" in names


def test_monthly_summary(temp_db):
    mgr = BudgetManager()
    mgr.add_entry(_entry("2026-07-01", 4_000_000, "income", "급여"))
    mgr.add_entry(_entry("2026-07-05", 1_000_000, "expense", "주거/관리비"))
    mgr.add_entry(_entry("2026-07-06", 500_000, "expense", "식비"))

    summary = BudgetAnalyzer().get_monthly_summary("2026-07")
    assert summary.total_income == 4_000_000
    assert summary.total_expense == 1_500_000
    assert summary.savings == 2_500_000
    assert abs(summary.savings_rate - 62.5) < 0.51  # 2.5M / 4M


def test_category_breakdown(temp_db):
    mgr = BudgetManager()
    mgr.add_entry(_entry("2026-08-01", 300_000, "expense", "식비"))
    mgr.add_entry(_entry("2026-08-02", 100_000, "expense", "교통"))

    df = BudgetAnalyzer().get_category_breakdown("2026-08")
    assert not df.empty
    assert list(df.columns) == ["category", "amount", "pct"]
    assert df["amount"].sum() == 400_000
    # 비중 합은 100%
    assert abs(df["pct"].sum() - 100.0) < 0.2


def test_investable_amount(temp_db):
    mgr = BudgetManager()
    mgr.add_entry(_entry("2026-09-01", 5_000_000, "income", "급여"))
    mgr.add_entry(_entry("2026-09-10", 2_000_000, "expense", "식비"))

    out = BudgetAnalyzer().calculate_investable_amount("2026-09")
    assert out["monthly_income"] == 5_000_000
    assert out["monthly_expense"] == 2_000_000
    assert out["monthly_savings"] == 3_000_000
    assert out["investable_amount"] >= 0
    # 비상자금(3개월치)의 1/12을 저축에서 차감
    assert out["emergency_reserve_needed"] == 6_000_000


def test_recurring_add_and_list(temp_db):
    rec = RecurringExpenseManager()
    rec.add_recurring(_entry("2026-05-25", 55_000, "expense", "통신",
                             description="휴대폰", recurring=1, day=25))
    items = rec.get_recurring_items()
    assert len(items) == 1
    assert items[0].category == "통신"
    assert items[0].is_recurring == 1


def test_recurring_auto_apply_is_idempotent(temp_db):
    rec = RecurringExpenseManager()
    rec.add_recurring(_entry("2026-05-25", 55_000, "expense", "통신",
                             description="휴대폰", recurring=1, day=25))

    first = rec.auto_apply_recurring("2026-06")
    second = rec.auto_apply_recurring("2026-06")
    # 같은 달에 두 번 적용해도 중복 생성되지 않아야 한다
    assert first >= 0
    assert second == 0


def test_recurring_remove(temp_db):
    rec = RecurringExpenseManager()
    eid = rec.add_recurring(_entry("2026-05-25", 9_900, "expense", "구독서비스",
                                   description="넷플릭스", recurring=1, day=25))
    assert len(rec.get_recurring_items()) == 1
    rec.remove_recurring(eid)
    assert rec.get_recurring_items() == []
