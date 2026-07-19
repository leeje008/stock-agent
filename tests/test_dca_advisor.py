from portfolio.dca_advisor import DcaAdvisor


def test_decide_weights_small_blend_sums_to_one():
    adv = DcaAdvisor()
    tickers = [{"ticker": "AAA", "name": "A", "market": "US"},
               {"ticker": "BBB", "name": "B", "market": "US"}]
    weights, strategy, rationale = adv._decide_weights(tickers, "중립", "2y")
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert set(weights) == {"AAA", "BBB"}
    assert strategy in ("heuristic_2asset", "heuristic_blend")
    assert isinstance(rationale, str) and rationale


def test_decide_weights_three_equal_base():
    adv = DcaAdvisor()
    tickers = [{"ticker": t, "name": t, "market": "US"} for t in ("AAA", "BBB", "CCC")]
    weights, strategy, _ = adv._decide_weights(tickers, "중립", "2y")
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert strategy == "heuristic_blend"
    # 매칭 종목이 없으면 동일가중 유지
    for w in weights.values():
        assert abs(w - 1 / 3) < 1e-6
