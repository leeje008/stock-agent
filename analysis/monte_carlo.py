import numpy as np


def simulate(
    initial_value: float,
    monthly_contribution: float,
    expected_annual_return: float,
    annual_volatility: float,
    years: int = 30,
    n_simulations: int = 1000,
    goal_amount: float | None = None,
) -> dict:
    """몬테카를로 시뮬레이션으로 포트폴리오 미래 가치 예측

    Returns:
        paths: (n_simulations, n_months+1) 배열
        percentiles: 10/25/50/75/90 분위 경로
        goal_probability: 목표 달성 확률 (goal_amount 지정 시)
    """
    monthly_return = expected_annual_return / 12
    monthly_vol = annual_volatility / np.sqrt(12)
    n_months = years * 12

    rng = np.random.default_rng(seed=42)
    random_returns = rng.normal(monthly_return, monthly_vol, (n_simulations, n_months))

    paths = np.zeros((n_simulations, n_months + 1))
    paths[:, 0] = initial_value

    for t in range(1, n_months + 1):
        paths[:, t] = paths[:, t - 1] * (1 + random_returns[:, t - 1]) + monthly_contribution

    final_values = paths[:, -1]
    total_invested = initial_value + monthly_contribution * n_months

    # 분위별 경로
    percentile_paths = {}
    for pct in [10, 25, 50, 75, 90]:
        percentile_paths[pct] = np.percentile(paths, pct, axis=0)

    result = {
        "paths": paths,
        "percentile_paths": percentile_paths,
        "final_median": float(np.median(final_values)),
        "final_mean": float(np.mean(final_values)),
        "final_p10": float(np.percentile(final_values, 10)),
        "final_p25": float(np.percentile(final_values, 25)),
        "final_p50": float(np.percentile(final_values, 50)),
        "final_p75": float(np.percentile(final_values, 75)),
        "final_p90": float(np.percentile(final_values, 90)),
        "total_invested": total_invested,
        "prob_positive": float(np.mean(final_values > total_invested)),
        "n_months": n_months,
        "years": years,
    }

    if goal_amount is not None:
        result["goal_amount"] = goal_amount
        result["prob_goal"] = float(np.mean(final_values >= goal_amount))
        # 중간값이 목표에 도달하는 시점
        median_path = percentile_paths[50]
        for t in range(n_months + 1):
            if median_path[t] >= goal_amount:
                result["median_time_to_goal_months"] = t
                result["median_time_to_goal_years"] = round(t / 12, 1)
                break

    return result
