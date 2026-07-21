from analysis import tax


def _txn(date, ticker, action, qty, price, fee=0.0, tax_amt=0.0, currency="KRW"):
    return {
        "date": date, "ticker": ticker, "name": ticker, "action": action,
        "quantity": qty, "price": price, "fee": fee, "tax": tax_amt,
        "currency": currency,
    }


def test_usd_gain_converted_to_krw():
    """외화 실현손익은 환율로 환산되어야 한다 (USD 이익을 원화로 착각하면 안 됨)."""
    txns = [
        _txn("2024-01-01", "AAPL", "BUY", 10, 100.0, currency="USD"),
        _txn("2024-02-01", "AAPL", "SELL", 10, 200.0, currency="USD"),
    ]
    realized = tax.realized_pnl_from_transactions(txns, fx_rate=1300.0)
    r = realized[0]
    assert r["currency"] == "USD"
    assert abs(r["gain"] - 1000.0) < 1e-6          # 거래 통화 기준
    assert abs(r["gain_krw"] - 1_300_000.0) < 1e-6  # 원화 환산
    assert abs(tax.total_realized_gain(realized) - 1_300_000.0) < 1e-6


def test_mixed_currency_total_is_krw():
    """KRW/USD 혼재 시 합계는 원화 기준으로 더해져야 한다."""
    txns = [
        _txn("2024-01-01", "005930", "BUY", 10, 70_000.0, currency="KRW"),
        _txn("2024-02-01", "005930", "SELL", 10, 80_000.0, currency="KRW"),
        _txn("2024-01-01", "AAPL", "BUY", 1, 100.0, currency="USD"),
        _txn("2024-02-01", "AAPL", "SELL", 1, 200.0, currency="USD"),
    ]
    realized = tax.realized_pnl_from_transactions(txns, fx_rate=1300.0)
    # KRW 100,000 + USD 100 × 1300 = 230,000
    assert abs(tax.total_realized_gain(realized) - 230_000.0) < 1e-6


def test_krw_unaffected_by_fx_rate():
    txns = [
        _txn("2024-01-01", "005930", "BUY", 1, 1000.0, currency="KRW"),
        _txn("2024-02-01", "005930", "SELL", 1, 1500.0, currency="KRW"),
    ]
    realized = tax.realized_pnl_from_transactions(txns, fx_rate=9999.0)
    assert abs(realized[0]["gain_krw"] - 500.0) < 1e-6


def test_capital_gains_below_deduction_is_zero():
    out = tax.capital_gains_tax(2_000_000)
    assert out["taxable"] == 0.0
    assert out["tax"] == 0.0
    assert out["deduction_used"] == 2_000_000


def test_capital_gains_above_deduction():
    out = tax.capital_gains_tax(5_000_000)
    assert out["deduction_used"] == 2_500_000
    assert out["taxable"] == 2_500_000
    assert abs(out["tax"] - 2_500_000 * 0.22) < 1e-6


def test_capital_gains_loss_is_zero():
    out = tax.capital_gains_tax(-1_000_000)
    assert out["taxable"] == 0.0 and out["tax"] == 0.0
    assert out["deduction_used"] == 0.0


def test_dividend_tax_and_comprehensive_flag():
    small = tax.dividend_tax(1_000_000)
    assert abs(small["tax"] - 154_000) < 1e-6
    assert small["comprehensive_taxation"] is False
    big = tax.dividend_tax(25_000_000)
    assert big["comprehensive_taxation"] is True
    # 음수 입력은 0으로 클램프
    assert tax.dividend_tax(-500)["tax"] == 0.0


def test_isa_exempt_limits():
    assert tax.isa_exempt_limit("general") == 2_000_000
    assert tax.isa_exempt_limit("reborn") == 4_000_000
    assert tax.isa_exempt_limit("flexible") == 2_000_000


def test_isa_benefit_within_and_over_limit():
    within = tax.isa_tax_benefit(1_500_000, "general")
    assert within["exempt_amount"] == 1_500_000
    assert within["taxable"] == 0.0 and within["tax"] == 0.0

    over = tax.isa_tax_benefit(3_000_000, "general")
    assert over["exempt_amount"] == 2_000_000
    assert over["taxable"] == 1_000_000
    assert abs(over["tax"] - 1_000_000 * 0.099) < 1e-6
    assert over["saved_vs_normal"] > 0

    loss = tax.isa_tax_benefit(-100_000)
    assert loss["tax"] == 0.0 and loss["exempt_amount"] == 0.0


def test_realized_pnl_moving_average():
    txns = [
        _txn("2024-01-15", "AAA", "BUY", 5, 100.0),
        _txn("2024-02-15", "AAA", "BUY", 5, 120.0),
        _txn("2024-03-15", "AAA", "SELL", 4, 150.0),
    ]
    realized = tax.realized_pnl_from_transactions(txns)
    assert len(realized) == 1
    r = realized[0]
    # 평균단가 110 → 원가 440, 매도대금 600, 이익 160
    assert abs(r["cost_basis"] - 440.0) < 1e-6
    assert abs(r["proceeds"] - 600.0) < 1e-6
    assert abs(r["gain"] - 160.0) < 1e-6


def test_realized_pnl_fees_reduce_gain():
    txns = [
        _txn("2024-01-15", "BBB", "BUY", 10, 50.0),
        _txn("2024-02-15", "BBB", "SELL", 10, 60.0, fee=10.0, tax_amt=5.0),
    ]
    r = tax.realized_pnl_from_transactions(txns)[0]
    assert abs(r["gain"] - (600.0 - 15.0 - 500.0)) < 1e-6


def test_realized_pnl_ignores_sell_without_position():
    txns = [_txn("2024-01-15", "CCC", "SELL", 3, 10.0)]
    assert tax.realized_pnl_from_transactions(txns) == []


def test_realized_pnl_empty():
    assert tax.realized_pnl_from_transactions([]) == []
    assert tax.total_realized_gain([]) == 0.0


def test_realized_pnl_from_db_transactions(temp_db):
    """DB 왕복 통합 검증 — 실제 컬럼(tx_date/note)이 정규화되어 시간순으로 계산되는지.

    업로드 순서가 역순(SELL 먼저 저장)이어도 거래일 기준으로 정렬되어야 한다.
    """
    from portfolio.manager import PortfolioManager

    pm = PortfolioManager()
    # 매도를 먼저 저장 (created_at 이 더 최신)
    pm.record_transactions_batch([{
        "date": "2024-02-01", "ticker": "AAPL", "name": "Apple", "action": "SELL",
        "quantity": 10, "price": 200.0, "amount": 2000.0, "fee": 0.0, "tax": 0.0,
        "currency": "USD", "market": "US",
    }])
    pm.record_transactions_batch([{
        "date": "2024-01-01", "ticker": "AAPL", "name": "Apple", "action": "BUY",
        "quantity": 10, "price": 100.0, "amount": 1000.0, "fee": 0.0, "tax": 0.0,
        "currency": "USD", "market": "US",
    }])

    rows = pm.get_all_transactions()
    # 정규화된 키가 존재하고 거래일 오름차순이어야 한다
    assert all("date" in r and "name" in r for r in rows)
    assert [r["date"] for r in rows] == ["2024-01-01", "2024-02-01"]
    assert rows[0]["name"] == "Apple"

    realized = tax.realized_pnl_from_transactions(rows)
    assert len(realized) == 1
    assert abs(realized[0]["gain"] - 1000.0) < 1e-6
    assert abs(tax.total_realized_gain(realized) - 1000.0) < 1e-6


def test_total_realized_gain_sums_losses():
    txns = [
        _txn("2024-01-01", "AAA", "BUY", 1, 100.0),
        _txn("2024-02-01", "AAA", "SELL", 1, 80.0),
        _txn("2024-03-01", "BBB", "BUY", 1, 100.0),
        _txn("2024-04-01", "BBB", "SELL", 1, 150.0),
    ]
    total = tax.total_realized_gain(tax.realized_pnl_from_transactions(txns))
    assert abs(total - 30.0) < 1e-6
