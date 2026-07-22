import streamlit as st
import plotly.graph_objects as go


def render(ctx):
    load_portfolio_data = ctx.load_portfolio_data
    st.subheader("몬테카를로 시뮬레이션")
    st.caption("현재 포트폴리오와 월 적립액을 기반으로 미래 자산을 시뮬레이션합니다.")

    # 기본값: 현재 포트폴리오 가치, 가계부 투자가능액, optimizer 수익률/변동성
    try:
        _, mc_port_df = load_portfolio_data()
        mc_initial = mc_port_df["평가금액(원)"].sum() if not mc_port_df.empty else 0
    except Exception:
        mc_initial = 0

    opt_result = st.session_state.get("optimization_result", {})
    default_return = opt_result.get("expected_return", 0.08)
    default_vol = opt_result.get("volatility", 0.15)

    col1, col2 = st.columns(2)
    with col1:
        mc_initial_val = st.number_input(
            "초기 투자금 (원)", value=int(mc_initial), step=1_000_000, format="%d", key="mc_init"
        )
        mc_monthly = st.number_input(
            "월 적립액 (원)", value=500_000, step=100_000, format="%d", key="mc_monthly"
        )
        mc_years = st.slider("투자 기간 (년)", min_value=1, max_value=40, value=20, key="mc_years")

    with col2:
        mc_return = st.number_input(
            "기대 연수익률", value=round(default_return, 4), step=0.01, format="%.4f", key="mc_return"
        )
        mc_vol = st.number_input(
            "연간 변동성", value=round(default_vol, 4), step=0.01, format="%.4f", key="mc_vol"
        )
        mc_goal = st.number_input(
            "목표 금액 (원)", value=1_000_000_000, step=100_000_000, format="%d", key="mc_goal"
        )

    if st.button("시뮬레이션 실행", type="primary", key="run_mc"):
        from ui.data_cache import simulate_cached

        with st.spinner("1,000회 시뮬레이션 실행 중..."):
            mc_result = simulate_cached(
                initial_value=mc_initial_val,
                monthly_contribution=mc_monthly,
                expected_annual_return=mc_return,
                annual_volatility=mc_vol,
                years=mc_years,
                n_simulations=1000,
                goal_amount=mc_goal,
            )

        # 결과 메트릭
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("목표 달성 확률", f"{mc_result['prob_goal']:.1%}")
        col2.metric("중간값 (50%)", f"{mc_result['final_p50']:,.0f}원")
        col3.metric("낙관적 (90%)", f"{mc_result['final_p90']:,.0f}원")
        col4.metric("비관적 (10%)", f"{mc_result['final_p10']:,.0f}원")

        if "median_time_to_goal_years" in mc_result:
            st.info(f"중간값 기준 목표 도달 시점: 약 {mc_result['median_time_to_goal_years']}년")

        # 팬 차트
        months = list(range(mc_result["n_months"] + 1))
        years_axis = [m / 12 for m in months]

        fig_mc = go.Figure()

        # 10-90 밴드
        fig_mc.add_trace(go.Scatter(
            x=years_axis, y=mc_result["percentile_paths"][90],
            mode="lines", line=dict(width=0), showlegend=False,
        ))
        fig_mc.add_trace(go.Scatter(
            x=years_axis, y=mc_result["percentile_paths"][10],
            mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor="rgba(100, 149, 237, 0.15)", name="10-90%",
        ))

        # 25-75 밴드
        fig_mc.add_trace(go.Scatter(
            x=years_axis, y=mc_result["percentile_paths"][75],
            mode="lines", line=dict(width=0), showlegend=False,
        ))
        fig_mc.add_trace(go.Scatter(
            x=years_axis, y=mc_result["percentile_paths"][25],
            mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor="rgba(100, 149, 237, 0.3)", name="25-75%",
        ))

        # 중간값
        fig_mc.add_trace(go.Scatter(
            x=years_axis, y=mc_result["percentile_paths"][50],
            mode="lines", line=dict(color="blue", width=2), name="중간값 (50%)",
        ))

        # 목표선
        fig_mc.add_hline(y=mc_goal, line_dash="dash", line_color="red",
                         annotation_text=f"목표: {mc_goal:,.0f}원")

        # 총 투자원금선
        invested_line = [mc_initial_val + mc_monthly * m for m in months]
        fig_mc.add_trace(go.Scatter(
            x=years_axis, y=invested_line,
            mode="lines", line=dict(color="gray", dash="dot"), name="총 투자원금",
        ))

        fig_mc.update_layout(
            title="포트폴리오 가치 시뮬레이션",
            xaxis_title="투자 기간 (년)",
            yaxis_title="포트폴리오 가치 (원)",
            hovermode="x unified",
            height=500,
        )
        st.plotly_chart(fig_mc, use_container_width=True)

        st.caption(f"총 투자원금: {mc_result['total_invested']:,.0f}원 | 수익 확률: {mc_result['prob_positive']:.1%}")
