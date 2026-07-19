import utils.fx as fx
from utils.helpers import format_currency, format_percent, read_cache, write_cache


def test_convert_to_krw_krw_passthrough():
    assert fx.convert_to_krw(1000.0, "KRW") == 1000.0


def test_convert_to_krw_usd(monkeypatch):
    monkeypatch.setattr(fx, "get_usd_krw_rate", lambda: 1300.0)
    assert fx.convert_to_krw(10.0, "USD") == 13000.0


def test_convert_to_usd(monkeypatch):
    monkeypatch.setattr(fx, "get_usd_krw_rate", lambda: 1300.0)
    assert fx.convert_to_usd(1300.0, "KRW") == 1.0
    assert fx.convert_to_usd(5.0, "USD") == 5.0


def test_format_currency():
    assert format_currency(1234567, "KRW") == "1,234,567원"
    assert format_currency(12.5, "USD") == "$12.50"


def test_format_percent():
    assert format_percent(0.1234) == "12.34%"


def test_cache_roundtrip():
    write_cache("test_key_ralph", {"v": 42})
    assert read_cache("test_key_ralph") == {"v": 42}
