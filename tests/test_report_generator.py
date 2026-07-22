from agent.report_generator import ReportGenerator


def test_save_and_get_latest(temp_db):
    rg = ReportGenerator()
    rg.save_report("market", "첫 리포트", {"score": 1})
    rg.save_report("market", "두번째 리포트", {"score": 2})

    latest = rg.get_latest_report("market")
    assert latest is not None
    assert latest["content"] == "두번째 리포트"
    assert '"score": 2' in latest["metadata_json"]


def test_get_latest_none_when_absent(temp_db):
    assert ReportGenerator().get_latest_report("nonexistent") is None


def test_get_report_history(temp_db):
    rg = ReportGenerator()
    for i in range(3):
        rg.save_report("debate", f"리포트 {i}")
    history = rg.get_report_history("debate", limit=10)
    assert len(history) == 3
    # 최신순 정렬
    assert history[0]["content"] == "리포트 2"


def test_report_type_isolation(temp_db):
    rg = ReportGenerator()
    rg.save_report("market", "시장")
    rg.save_report("fundamental", "펀더멘탈")
    assert rg.get_latest_report("market")["content"] == "시장"
    assert rg.get_latest_report("fundamental")["content"] == "펀더멘탈"
    assert len(rg.get_report_history("market")) == 1
