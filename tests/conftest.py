"""테스트 공용 픽스처.

DB 의존 테스트는 임시 SQLite 파일로 격리해 실제 data/stock_agent.db 를 건드리지 않는다.
"""
import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """db.database.DB_PATH 를 임시 파일로 교체하고 스키마를 초기화한다."""
    import db.database as database

    db_file = tmp_path / "test_stock_agent.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    database.init_db()
    database.init_budget_defaults()
    return str(db_file)
