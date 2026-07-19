import streamlit as st
from utils.constants import DISCLAIMER


def render(ctx):
    pm = ctx.pm
    holdings = pm.get_all_holdings()

    st.subheader("Bull vs Bear AI 토론")
    st.caption("강세론자와 약세론자 AI가 현재 포트폴리오와 시장에 대해 토론합니다.")

    if not holdings:
        st.info("포트폴리오에 종목을 추가하세요.")
    else:
        if st.button("AI 토론 시작 (3라운드)"):
            try:
                from agent.debate import DebateAgent

                debate = DebateAgent()
                portfolio_summary = pm.get_portfolio_summary()
                news_analysis = st.session_state.get("news_analysis", {})
                macro_data = st.session_state.get("macro_data", {})

                with st.spinner("AI 토론 진행 중 (qwen3.5:27b x 3라운드)... 약 1분 소요"):
                    result = debate.run_debate(portfolio_summary, news_analysis, macro_data)

                st.session_state["debate_result"] = result
            except Exception as e:
                st.error(f"AI 토론 실패: {e}")

        if "debate_result" in st.session_state:
            result = st.session_state["debate_result"]

            verdict = result.get("final_verdict", "neutral")
            verdict_emoji = {"bullish": "🟢 강세", "neutral": "🟡 중립", "bearish": "🔴 약세"}
            st.metric("최종 판정", verdict_emoji.get(verdict, verdict))

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 🐂 강세론 (Bull)")
                st.markdown(result.get("bull_case", ""))
            with col2:
                st.markdown("### 🐻 약세론 (Bear)")
                st.markdown(result.get("bear_case", ""))

            st.divider()
            st.markdown("### ⚖️ 종합 판정 (Moderator)")
            st.markdown(result.get("synthesis", ""))

            st.divider()
            st.caption(DISCLAIMER)
