import streamlit as st
import pandas as pd
from utils.constants import RISK_LEVELS
from utils.constants import DISCLAIMER


def render(ctx):
    pm = ctx.pm
    isa_mgr = ctx.isa_mgr
    isa_account = ctx.isa_account
    budget = ctx.budget
    holdings = pm.get_all_holdings()

    # --- ISA DCA 가이드 (상단, 항상 사용 가능) ---
    st.subheader("ISA 월간 매수 가이드 (DCA)")
    st.caption(
        f"계좌: {isa_account.account_name} · 월 적립금: "
        f"{isa_account.monthly_contribution:,.0f}원 · 위험성향: {isa_account.risk_level}"
    )

    if not holdings:
        st.info("사이드바에서 종목을 추가하세요. (S&P/NASDAQ ETF 권장)")
    else:
        dca_tickers = [
            {"ticker": h.ticker, "name": h.name, "market": h.market}
            for h in holdings
        ]
        dca_amount = st.number_input(
            "이번 달 추천 산출 금액 (원)",
            value=int(isa_account.monthly_contribution),
            step=100_000, format="%d", key="dca_amount_input",
        )
        dca_risk = st.selectbox(
            "위험성향", options=list(RISK_LEVELS.keys()),
            index=list(RISK_LEVELS.keys()).index(isa_account.risk_level)
                  if isa_account.risk_level in RISK_LEVELS else 2,
            key="dca_risk_input",
        )

        if st.button("DCA 추천 산출", key="dca_run_btn"):
            try:
                from portfolio.dca_advisor import DcaAdvisor
                advisor = DcaAdvisor()
                with st.spinner("종목별 가격 조회 + 비중 계산 중..."):
                    plan = advisor.recommend(
                        tickers=dca_tickers,
                        monthly_amount=float(dca_amount),
                        risk_level=dca_risk,
                    )
                st.session_state["dca_plan"] = plan.to_summary()
                st.session_state["dca_plan_obj"] = {
                    "weights_json": plan.weights_json,
                    "monthly_amount": plan.monthly_amount,
                    "strategy": plan.strategy,
                }
            except Exception as e:
                st.error(f"DCA 추천 실패: {e}")

        if "dca_plan" in st.session_state:
            plan_data = st.session_state["dca_plan"]
            st.success(f"전략: **{plan_data['strategy']}** — {plan_data['rationale']}")
            rows = plan_data["rows"]
            df_show = pd.DataFrame([
                {
                    "종목": f"{r['name']} ({r['ticker']})",
                    "비중": f"{r['weight']*100:.1f}%",
                    "목표 금액(원)": f"{r['target_amount_krw']:,.0f}",
                    "현재가": f"{r['price']:,.2f} {r['currency']}",
                    "매수 수량": r["shares"],
                    "실투자(원)": f"{r['spent_krw']:,.0f}",
                }
                for r in rows
            ])
            st.dataframe(df_show, use_container_width=True, hide_index=True)
            col_x, col_y = st.columns(2)
            col_x.metric("투자 금액 합계",
                         f"{sum(r['spent_krw'] for r in rows):,.0f}원")
            col_y.metric("잔여 현금", f"{plan_data['leftover_krw']:,.0f}원")

            if st.button("이 비중을 목표 비중으로 저장", key="dca_save_btn"):
                from datetime import datetime as _dt
                from db.models import TargetAllocationHistory
                obj = st.session_state["dca_plan_obj"]
                isa_mgr.record_target_allocation(TargetAllocationHistory(
                    account_id=isa_account.id,
                    set_date=_dt.today().strftime("%Y-%m-%d"),
                    weights_json=obj["weights_json"],
                    monthly_amount=obj["monthly_amount"],
                    strategy=obj["strategy"],
                    reason=f"DCA 추천 ({plan_data['risk_level']})",
                ))
                st.success("목표 비중 저장 완료 (target_allocation_history)")

    st.divider()

    # --- 기존 최적화 결과 기반 매수 가이드 ---
    if not holdings:
        st.info("포트폴리오에 종목을 추가하고 최적화를 실행하세요.")
    elif "optimization_result" not in st.session_state:
        st.info("'최적화 결과' 탭에서 최적화를 실행하면 추가 가이드가 표시됩니다.")
    else:
        result = st.session_state["optimization_result"]

        st.subheader(f"최적화 기반 매수 가이드 (사이드바 예산 {budget:,.0f}원)")

        buy_guide = result.get("buy_guide", {})
        if buy_guide:
            guide_df = pd.DataFrame(
                [{"종목": k, "매수 수량": v} for k, v in buy_guide.items()]
            )
            st.dataframe(guide_df, use_container_width=True, hide_index=True)

            col1, col2 = st.columns(2)
            col1.metric("투자 금액", f"{result.get('invested', 0):,.0f}원")
            col2.metric("잔여 현금", f"{result.get('leftover', 0):,.0f}원")
        else:
            st.warning("예산 내 매수 가능한 종목이 없습니다.")

        # AI 종합 리포트
        st.divider()
        if st.button("AI 종합 리포트 생성"):
            try:
                from agent.market_analyst import PortfolioManagerAgent
                from agent.report_generator import ReportGenerator

                agent = PortfolioManagerAgent()
                report_gen = ReportGenerator()
                portfolio_summary = pm.get_portfolio_summary()
                news_analysis = st.session_state.get("news_analysis", {})
                macro_data = st.session_state.get("macro_data", {})

                with st.spinner("AI 리포트 생성 중 (qwen3.5:27b)..."):
                    report = agent.generate_recommendation(
                        current_portfolio=portfolio_summary,
                        optimization_result=result,
                        news_analysis=news_analysis,
                        macro_data=macro_data,
                        budget=budget,
                    )

                st.session_state["ai_report"] = report
                # 리포트 저장
                report_gen.save_report("recommendation", report, metadata={
                    "strategy": result.get("strategy"),
                    "budget": budget,
                })
            except Exception as e:
                st.error(f"AI 리포트 생성 실패: {e}")

        if "ai_report" in st.session_state:
            st.markdown("### AI 투자 추천 리포트")
            st.markdown(st.session_state["ai_report"])

            # 리포트 다운로드
            st.download_button(
                label="리포트 다운로드 (Markdown)",
                data=st.session_state["ai_report"],
                file_name="investment_report.md",
                mime="text/markdown",
            )

        # 리포트 히스토리
        st.divider()
        with st.expander("과거 리포트 보기"):
            try:
                from agent.report_generator import ReportGenerator
                report_gen = ReportGenerator()
                history = report_gen.get_report_history("recommendation", limit=10)
                if history:
                    for i, report in enumerate(history):
                        with st.expander(f"리포트 #{i+1} — {report.get('created_at', 'N/A')}"):
                            st.markdown(report.get("content", ""))
                else:
                    st.info("저장된 리포트가 없습니다.")
            except Exception:
                st.info("리포트 히스토리를 불러올 수 없습니다.")

        st.divider()
        st.caption(DISCLAIMER)
