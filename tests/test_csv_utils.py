import numpy as np
import pandas as pd

from utils.csv_utils import parse_date, parse_number, read_csv_with_fallback


def test_parse_number():
    assert parse_number("1,234") == 1234.0
    assert parse_number("  12 ") == 12.0
    assert parse_number(35) == 35.0
    assert parse_number(np.nan) == 0.0
    assert parse_number("n/a") == 0.0


def test_parse_date_variants():
    assert parse_date("20240115") == "2024-01-15"
    assert parse_date("2024-01-15") == "2024-01-15"
    assert parse_date("2024.01.15") == "2024-01-15"
    assert parse_date(pd.Timestamp("2024-01-15")) == "2024-01-15"


def test_read_csv_with_fallback_encodings():
    df = pd.DataFrame({"종목명": ["삼성전자"], "수량": [10]})
    # cp949 로 저장된 바이트를 폴백으로 읽어낸다 (utf-8 먼저 시도 → 실패 → cp949)
    data_cp949 = df.to_csv(index=False).encode("cp949")
    out = read_csv_with_fallback(data_cp949, ["utf-8", "cp949", "euc-kr"])
    assert out is not None
    assert list(out.columns) == ["종목명", "수량"]
    assert out["종목명"].iloc[0] == "삼성전자"


def test_read_csv_with_fallback_no_encoding_returns_none():
    # 시도할 인코딩이 없으면 None
    assert read_csv_with_fallback(b"a,b\n1,2", []) is None


def test_broker_template_roundtrip_preserved():
    from broker.csv_parser import BrokerCSVParser
    tmpl = BrokerCSVParser.generate_template()
    data = tmpl.to_csv(index=False).encode("utf-8")
    parser = BrokerCSVParser()
    txns = parser.parse(data, "template.csv", "범용 (직접입력)")
    assert len(txns) == 3
    first = txns[0]
    assert first["ticker"] == "133690"
    assert first["action"] == "BUY"
    assert first["quantity"] == 5
    assert first["price"] == 80000.0
    assert first["date"] == "2024-01-15"


def test_budget_template_roundtrip_preserved():
    from budget.csv_parser import BankCSVParser
    tmpl = BankCSVParser.generate_template()
    data = tmpl.to_csv(index=False).encode("utf-8")
    parser = BankCSVParser()
    entries = parser.parse(data, "template.csv")
    assert len(entries) >= 1
    assert all("amount" in e and "type" in e for e in entries)
