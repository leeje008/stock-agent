import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render(ctx):
    pm = ctx.pm
    tracker = ctx.tracker
    load_portfolio_data = ctx.load_portfolio_data
    holdings, df = load_portfolio_data()

    if not holdings:
        st.info("보유 종목이 없습니다. 사이드바에서 종목을 추가하세요.")
    else:
        # 요약 지표
        col1, col2, col3, col4 = st.columns(4)
        total_value = df["평가금액(원)"].sum()
        total_cost = df["매입금액(원)"].sum()
        total_pnl = total_value - total_cost
        total_return = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        col1.metric("총 평가금액", f"{total_value:,.0f}원")
        col2.metric("총 손익", f"{total_pnl:,.0f}원")
        col3.metric("총 수익률", f"{total_return:.2f}%")
        col4.metric("보유 종목 수", f"{len(holdings)}개")

        # 포트폴리오 스냅샷 저장
        try:
            snapshot_holdings = df[["종목명", "티커", "평가금액(원)", "수익률(%)"]].to_dict("records")
            tracker.take_snapshot(total_value, total_cost, snapshot_holdings)
        except Exception:
            pass

        # 종목 테이블
        display_cols = ["종목명", "티커", "시장", "수량", "평균매입가", "현재가", "통화", "평가금액(원)", "손익(원)", "수익률(%)", "섹터"]
        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
        )

        # 차트
        col_a, col_b = st.columns(2)
        with col_a:
            fig_market = px.pie(df, names="시장", values="평가금액(원)", title="시장별 비중")
            st.plotly_chart(fig_market, use_container_width=True)
        with col_b:
            sector_df = df.groupby("섹터")["평가금액(원)"].sum().reset_index()
            fig_sector = px.pie(sector_df, names="섹터", values="평가금액(원)", title="섹터별 비중")
            st.plotly_chart(fig_sector, use_container_width=True)

        # 성과 추적 차트
        history = tracker.get_history(days=90)
        if len(history) >= 2:
            st.subheader("포트폴리오 성과 추이")
            hist_df = pd.DataFrame(history)
            fig_perf = go.Figure()
            fig_perf.add_trace(go.Scatter(
                x=hist_df["date"], y=hist_df["total_value"],
                mode="lines", name="평가금액", line=dict(color="blue"),
            ))
            fig_perf.add_trace(go.Scatter(
                x=hist_df["date"], y=hist_df["total_cost"],
                mode="lines", name="매입금액", line=dict(color="gray", dash="dash"),
            ))
            fig_perf.update_layout(
                yaxis_title="금액 (원)",
                xaxis_title="날짜",
                hovermode="x unified",
            )
            st.plotly_chart(fig_perf, use_container_width=True)

        # 종목 삭제
        st.subheader("종목 관리")
        del_id = st.selectbox(
            "삭제할 종목",
            options=[(r["ID"], f"{r['종목명']} ({r['티커']})") for _, r in df.iterrows()],
            format_func=lambda x: x[1],
        )
        if st.button("선택 종목 삭제"):
            pm.remove_holding(del_id[0])
            st.success("삭제 완료!")
            st.rerun()

        # 배당 요약
        st.divider()
        st.subheader("배당 수익 요약")
        try:
            from analysis.dividend import get_portfolio_dividend_summary
            div_summary = get_portfolio_dividend_summary(holdings)
            st.metric("예상 연간 배당수입", f"{div_summary['total_annual_income_krw']:,.0f}원")

            div_rows = []
            for d in div_summary["holdings"]:
                if d["dividend_yield"] > 0:
                    div_rows.append({
                        "종목": d["name"],
                        "배당수익률": f"{d['dividend_yield']:.2%}",
                        "연간 배당금": f"{d['annual_income_krw']:,.0f}원",
                        "배당일": d["ex_dividend_date"] or "-",
                    })
            if div_rows:
                st.dataframe(pd.DataFrame(div_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("배당 정보가 있는 종목이 없습니다.")
        except Exception as e:
            st.caption(f"배당 정보 조회 실패: {e}")

        # 리밸런싱 드리프트 알림
        try:
            from portfolio.rebalancer import Rebalancer
            rebalancer = Rebalancer()
            targets = rebalancer.get_targets()
            if targets:
                st.divider()
                st.subheader("리밸런싱 알림")
                target_strategy = rebalancer.get_target_strategy()
                st.caption(f"목표 전략: {target_strategy}")

                # 현재 비중 계산
                total_val = df["평가금액(원)"].sum()
                if total_val > 0:
                    current_weights = {}
                    for _, row in df.iterrows():
                        current_weights[row["티커"]] = row["평가금액(원)"] / total_val

                    drift_alerts = rebalancer.check_drift(current_weights)
                    if drift_alerts:
                        drift_rows = []
                        for a in drift_alerts:
                            drift_rows.append({
                                "종목": a["ticker"],
                                "현재 비중": f"{a['current']:.1%}",
                                "목표 비중": f"{a['target']:.1%}",
                                "드리프트": f"{a['drift']:+.1%}",
                                "조치": a["action"],
                            })
                        st.dataframe(pd.DataFrame(drift_rows), use_container_width=True, hide_index=True)
                    else:
                        st.success("포트폴리오가 목표 비중에 잘 맞춰져 있습니다.")
        except Exception:
            pass
