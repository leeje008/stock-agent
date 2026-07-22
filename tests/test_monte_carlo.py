import numpy as np

from analysis.monte_carlo import simulate


def test_simulate_deterministic():
    """seed=42 고정이라 동일 입력은 동일 결과를 낸다."""
    a = simulate(1_000_000, 500_000, 0.07, 0.15, years=10, n_simulations=500)
    b = simulate(1_000_000, 500_000, 0.07, 0.15, years=10, n_simulations=500)
    assert a["final_median"] == b["final_median"]
    assert np.array_equal(a["paths"], b["paths"])


def test_simulate_return_keys():
    r = simulate(1_000_000, 300_000, 0.06, 0.12, years=5, n_simulations=300)
    for k in ("paths", "percentile_paths", "final_median", "final_mean",
              "final_p10", "final_p50", "final_p90", "total_invested",
              "prob_positive", "n_months", "years"):
        assert k in r
    assert set(r["percentile_paths"]) == {10, 25, 50, 75, 90}
    assert r["n_months"] == 60
    # 경로 형태: (n_simulations, n_months + 1)
    assert r["paths"].shape == (300, 61)


def test_simulate_goal_probability_bounds():
    r = simulate(1_000_000, 500_000, 0.08, 0.15, years=20,
                 n_simulations=500, goal_amount=1_000_000_000)
    assert 0.0 <= r["prob_goal"] <= 1.0
    assert r["goal_amount"] == 1_000_000_000


def test_simulate_total_invested():
    r = simulate(1_000_000, 100_000, 0.05, 0.1, years=3, n_simulations=100)
    # 초기 + 월적립 × 개월수
    assert r["total_invested"] == 1_000_000 + 100_000 * 36


def test_simulate_zero_volatility_no_error():
    r = simulate(1_000_000, 0, 0.05, 0.0, years=2, n_simulations=50)
    # 변동성 0이면 모든 경로가 동일 → 분위가 모두 같음
    assert np.isfinite(r["final_median"])
    assert r["final_p10"] == r["final_p90"]


def test_simulate_boundary_inputs_no_error():
    # 음수/0 등 비정상 입력에서도 예외 없이 유한 결과
    r = simulate(-100, -50, 0.05, -0.2, years=0, n_simulations=0)
    assert np.isfinite(r["final_median"])
    assert r["n_months"] == 12          # years 0 → 최소 1년
    assert r["paths"].shape[0] == 1     # n_simulations 0 → 최소 1회
    assert r["total_invested"] >= 0     # 음수 입력이 0으로 클램프
