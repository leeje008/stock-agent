import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def render(ctx):
    pm = ctx.pm
    fetcher = ctx.fetcher
    holdings = pm.get_all_holdings()

    if len(holdings) < 2:
        st.info("백테스팅을 실행하려면 최소 2개 이상의 종목이 필요합니다.")
    else:
        st.subheader("전략 백테스팅")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            bt_period = st.selectbox("데이터 기간", ["1y", "2y", "5y"], index=1, key="bt_period")
        with col2:
            bt_lookback = st.number_input("룩백 기간 (일)", value=252, min_value=60, max_value=504, key="bt_lookback")
        with col3:
            bt_rebalance = st.number_input("리밸런싱 주기 (일)", value=63, min_value=21, max_value=252, key="bt_rebalance")
        with col4:
            bt_cost_bps = st.number_input("거래비용 (bps)", value=0, min_value=0, max_value=100, key="bt_cost_bps",
                                          help="리밸런싱 회전율에 부과. 10bps = 0.1%")

        if st.button("백테스팅 실행", type="primary"):
            try:
                from analysis.backtest import Backtester

                tickers_data = [{"ticker": h.ticker, "market": h.market} for h in holdings]
                with st.spinner("시세 데이터 수집 중..."):
                    prices = fetcher.get_multiple_prices(tickers_data, bt_period)

                if prices.empty or len(prices.columns) < 2:
                    st.error("시세 데이터가 부족합니다.")
                else:
                    bt = Backtester(prices)
                    with st.spinner("3개 전략 백테스팅 중..."):
                        results = bt.compare_strategies(
                            lookback_days=bt_lookback,
                            rebalance_days=bt_rebalance,
                            cost_bps=float(bt_cost_bps),
                        )

                    st.session_state["backtest_results"] = results
            except Exception as e:
                st.error(f"백테스팅 실패: {e}")

        if "backtest_results" in st.session_state:
            results = st.session_state["backtest_results"]

            # 성과 비교 테이블
            st.markdown("### 전략별 성과 비교")
            strat_names = {
                "max_sharpe": "최대 샤프",
                "min_volatility": "최소 변동성",
                "hrp": "HRP",
                "min_cvar": "최소 CVaR",
                "equal_weight": "동일 비중",
            }
            perf_rows = []
            for r in results:
                if "error" in r:
                    continue
                perf_rows.append({
                    "전략": strat_names.get(r["strategy"], r["strategy"]),
                    "총 수익률": f"{r['total_return']:.2%}",
                    "총 수익률(비용반영)": f"{r.get('net_total_return', r['total_return']):.2%}",
                    "연환산 수익률": f"{r['annualized_return']:.2%}",
                    "변동성": f"{r['volatility']:.2%}",
                    "샤프 비율": f"{r['sharpe_ratio']:.2f}",
                    "소르티노": f"{r.get('sortino_ratio', 0):.2f}",
                    "칼마": f"{r.get('calmar_ratio', 0):.2f}",
                    "승률": f"{r.get('win_rate', 0):.1%}",
                    "회전율": f"{r.get('turnover', 0):.2f}",
                    "최대 낙폭": f"{r['max_drawdown']:.2%}",
                })
            if perf_rows:
                st.dataframe(pd.DataFrame(perf_rows), use_container_width=True, hide_index=True)
                st.caption("'총 수익률(비용반영)'은 리밸런싱 회전율 × 거래비용(bps)을 차감한 net 성과입니다.")

            # 자산 곡선 차트
            st.markdown("### 자산 곡선 (초기값 = 1)")
            fig_bt = go.Figure()
            colors = ["blue", "orange", "green", "red", "purple"]
            for i, r in enumerate(results):
                if "error" in r or "equity_curve" not in r:
                    continue
                eq = r["equity_curve"]
                fig_bt.add_trace(go.Scatter(
                    x=eq.index, y=eq.values,
                    mode="lines",
                    name=strat_names.get(r["strategy"], r["strategy"]),
                    line=dict(color=colors[i % len(colors)]),
                ))
            fig_bt.update_layout(
                yaxis_title="포트폴리오 가치",
                xaxis_title="날짜",
                hovermode="x unified",
            )
            st.plotly_chart(fig_bt, use_container_width=True, key="bt_equity_curve")

            # 롤링 샤프 / 변동성 차트
            st.markdown("### 롤링 지표 (연율화)")
            fig_roll = go.Figure()
            for i, r in enumerate(results):
                if "error" in r or "rolling_sharpe" not in r:
                    continue
                rs = r["rolling_sharpe"].dropna()
                if rs.empty:
                    continue
                fig_roll.add_trace(go.Scatter(
                    x=rs.index, y=rs.values, mode="lines",
                    name=f"{strat_names.get(r['strategy'], r['strategy'])} 샤프",
                    line=dict(color=colors[i % len(colors)]),
                ))
            fig_roll.update_layout(
                yaxis_title="롤링 샤프", xaxis_title="날짜", hovermode="x unified",
            )
            st.plotly_chart(fig_roll, use_container_width=True, key="bt_rolling_sharpe")

            fig_rvol = go.Figure()
            for i, r in enumerate(results):
                if "error" in r or "rolling_vol" not in r:
                    continue
                rv = r["rolling_vol"].dropna()
                if rv.empty:
                    continue
                fig_rvol.add_trace(go.Scatter(
                    x=rv.index, y=rv.values, mode="lines",
                    name=f"{strat_names.get(r['strategy'], r['strategy'])} 변동성",
                    line=dict(color=colors[i % len(colors)]),
                ))
            fig_rvol.update_layout(
                yaxis_title="롤링 변동성(연율)", xaxis_title="날짜",
                yaxis_tickformat=".0%", hovermode="x unified",
            )
            st.plotly_chart(fig_rvol, use_container_width=True, key="bt_rolling_vol")
