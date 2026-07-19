from broker.aggregator import TransactionAggregator


def _txn(date, ticker, name, action, qty, price):
    return {
        "date": date, "ticker": ticker, "name": name, "action": action,
        "quantity": qty, "price": price, "amount": qty * price, "fee": 0.0, "tax": 0.0,
    }


def test_aggregate_weighted_average_dca():
    txns = [
        _txn("2024-01-15", "AAA", "Alpha", "BUY", 5, 100.0),
        _txn("2024-02-15", "AAA", "Alpha", "BUY", 5, 120.0),
    ]
    out = TransactionAggregator().aggregate(txns)
    assert len(out) == 1
    h = out[0]
    assert h["quantity"] == 10
    # 가중평균 = (5*100 + 5*120)/10 = 110
    assert h["avg_price"] == 110.0
    assert h["total_cost"] == 1100.0
    assert h["buy_count"] == 2
    assert h["first_buy_date"] == "2024-01-15"
    assert h["last_buy_date"] == "2024-02-15"


def test_aggregate_sell_reduces_position():
    txns = [
        _txn("2024-01-15", "BBB", "Beta", "BUY", 10, 50.0),
        _txn("2024-03-15", "BBB", "Beta", "SELL", 4, 60.0),
    ]
    out = TransactionAggregator().aggregate(txns)
    assert len(out) == 1
    assert out[0]["quantity"] == 6
    assert out[0]["sell_count"] == 1


def test_aggregate_fully_sold_excluded():
    txns = [
        _txn("2024-01-15", "CCC", "Gamma", "BUY", 3, 10.0),
        _txn("2024-02-15", "CCC", "Gamma", "SELL", 3, 12.0),
    ]
    out = TransactionAggregator().aggregate(txns)
    assert out == []
