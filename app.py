import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from db.database import init_db
from db.models import Holding, Transaction
from portfolio.manager import PortfolioManager
from portfolio.allocator import BudgetAllocator
from data.fetcher import StockDataFetcher
from data.market_data import MarketDataProcessor
from utils.constants import RISK_LEVELS, DISCLAIMER

# --- 초기 설정 ---
st.set_page_config(page_title="주식 포트폴리오 에이전트", layout="wide")
init_db()

pm = PortfolioManager()
fetcher = StockDataFetcher()
market_proc = MarketDataProcessor()


# --- 사이드바 ---
with st.sidebar:
    st.header("설정")

    budget = st.number_input(
        "추가 투자 예산 (원)", value=1_000_000, step=100_000, format="%d"
    )
    risk_level = st.select_slider(
        "위험 선호도",
        options=list(RISK_LEVELS.keys()),
        value="중립",
    )
    strategy = st.radio(
        "최적화 전략",
        options=["최대 샤프 비율", "최소 변동성"],
        index=0,
    )

    st.divider()

    st.subheader("종목 추가")
    with st.form("add_holding_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_ticker = st.text_input("티커", placeholder="AAPL 또는 005930")
        with col2:
            new_market = st.selectbox("시장", ["US", "KR", "ETF"])
        new_name = st.text_input("종목명", placeholder="Apple Inc.")
        col3, col4 = st.columns(2)
        with col3:
            new_qty = st.number_input("수량", min_value=1, value=1)
        with col4:
            new_price = st.number_input("평균매입가", min_value=0.0, value=0.0, format="%.2f")
        new_sector = st.text_input("섹터 (선택)", placeholder="Technology")
        submitted = st.form_submit_button("추가")

        if submitted and new_ticker and new_name:
            holding = Holding(
                ticker=new_ticker.strip().upper(),
                market=new_market,
                name=new_name.strip(),
                quantity=new_qty,
                avg_price=new_price,
                currency="USD" if new_market in ("US", "ETF") else "KRW",
                sector=new_sector or None,
            )
            pm.add_holding(holding)
            st.success(f"{new_name} 추가 완료!")
            st.rerun()

    st.divider()
    st.caption(DISCLAIMER)


# --- 메인 영역 ---
st.title("주식 포트폴리오 에이전트")

tab1, tab2, tab3, tab4 = st.tabs(
    ["포트폴리오 현황", "최적화 결과", "뉴스 & 시장 분석", "매수 가이드"]
)

# === Tab 1: 포트폴리오 현황 ===
with tab1:
    holdings = pm.get_all_holdings()

    if not holdings:
        st.info("보유 종목이 없습니다. 사이드바에서 종목을 추가하세요.")
    else:
        # 현재가 조회
        rows = []
        for h in holdings:
            current_price = None
            try:
                price_df = fetcher.get_price_data(h.ticker, h.market, period="5d")
                if not price_df.empty:
                    close_col = "Close" if "Close" in price_df.columns else "종가"
                    current_price = float(price_df[close_col].iloc[-1])
            except Exception:
                pass

            total_cost = h.avg_price * h.quantity
            total_value = (current_price or h.avg_price) * h.quantity
            pnl = total_value - total_cost
            pnl_pct = (pnl / total_cost * 100) if total_cost > 0 else 0

            rows.append({
                "ID": h.id,
                "종목명": h.name,
                "티커": h.ticker,
                "시장": h.market,
                "수량": h.quantity,
                "평균매입가": h.avg_price,
                "현재가": current_price or h.avg_price,
                "평가금액": total_value,
                "손익": pnl,
                "수익률(%)": round(pnl_pct, 2),
                "섹터": h.sector or "N/A",
            })

        df = pd.DataFrame(rows)

        # 요약 지표
        col1, col2, col3 = st.columns(3)
        total_value = df["평가금액"].sum()
        total_cost = (df["평균매입가"] * df["수량"]).sum()
        total_pnl = total_value - total_cost
        col1.metric("총 평가금액", f"{total_value:,.0f}")
        col2.metric("총 손익", f"{total_pnl:,.0f}")
        col3.metric("보유 종목 수", f"{len(holdings)}개")

        # 종목 테이블
        st.dataframe(
            df.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True,
        )

        # 차트
        col_a, col_b = st.columns(2)
        with col_a:
            fig_market = px.pie(df, names="시장", values="평가금액", title="시장별 비중")
            st.plotly_chart(fig_market, use_container_width=True)
        with col_b:
            sector_df = df.groupby("섹터")["평가금액"].sum().reset_index()
            fig_sector = px.pie(sector_df, names="섹터", values="평가금액", title="섹터별 비중")
            st.plotly_chart(fig_sector, use_container_width=True)

        # 종목 삭제
        st.subheader("종목 관리")
        del_id = st.selectbox(
            "삭제할 종목",
            options=[(r["ID"], f"{r['종목명']} ({r['티커']})") for r in rows],
            format_func=lambda x: x[1],
        )
        if st.button("선택 종목 삭제"):
            pm.remove_holding(del_id[0])
            st.success("삭제 완료!")
            st.rerun()


# === Tab 2: 최적화 결과 ===
with tab2:
    holdings = pm.get_all_holdings()

    if len(holdings) < 2:
        st.info("최적화를 실행하려면 최소 2개 이상의 종목이 필요합니다.")
    else:
        if st.button("최적화 실행", type="primary"):
            tickers = [{"ticker": h.ticker, "market": h.market} for h in holdings]
            allocator = BudgetAllocator()

            strat = "max_sharpe" if strategy == "최대 샤프 비율" else "min_volatility"

            with st.spinner("포트폴리오 최적화 중..."):
                result = allocator.generate_buy_guide(tickers, budget, strategy=strat)

            if "error" in result:
                st.error(result["error"])
            else:
                st.session_state["optimization_result"] = result

        if "optimization_result" in st.session_state:
            result = st.session_state["optimization_result"]

            col1, col2, col3 = st.columns(3)
            col1.metric("기대 수익률", f"{result['expected_return']:.2%}")
            col2.metric("변동성", f"{result['volatility']:.2%}")
            col3.metric("샤프 비율", f"{result['sharpe_ratio']:.2f}")

            # 최적 비중 차트
            weights_df = pd.DataFrame(
                list(result["optimal_weights"].items()),
                columns=["종목", "비중"],
            )
            fig_weights = px.bar(
                weights_df, x="종목", y="비중", title="최적 포트폴리오 비중"
            )
            fig_weights.update_layout(yaxis_tickformat=".1%")
            st.plotly_chart(fig_weights, use_container_width=True)


# === Tab 3: 뉴스 & 시장 분석 ===
with tab3:
    st.subheader("시장 분석")

    holdings = pm.get_all_holdings()
    tickers = [h.ticker for h in holdings]

    if not tickers:
        st.info("포트폴리오에 종목을 추가하면 뉴스 분석을 실행할 수 있습니다.")
    else:
        if st.button("AI 뉴스 분석 실행"):
            try:
                from agent.news_analyzer import NewsAnalystAgent

                agent = NewsAnalystAgent()

                # 실제 뉴스 API 연동 전 샘플 데이터
                sample_news = [
                    {
                        "title": "연준, 기준금리 동결 결정",
                        "summary": "미 연방준비제도가 기준금리를 현 수준에서 동결하기로 결정했다.",
                        "source": "Reuters",
                        "date": "2026-03-21",
                    },
                ]

                with st.spinner("뉴스 분석 중..."):
                    analysis = agent.analyze_news(sample_news, tickers)

                st.session_state["news_analysis"] = analysis
            except ValueError as e:
                st.error(str(e))

        if "news_analysis" in st.session_state:
            analysis = st.session_state["news_analysis"]

            sentiment = analysis.get("market_sentiment", "neutral")
            score = analysis.get("sentiment_score", 0)

            col1, col2 = st.columns(2)
            with col1:
                sentiment_emoji = {"bullish": "🟢", "neutral": "🟡", "bearish": "🔴"}
                st.metric(
                    "시장 감성",
                    f"{sentiment_emoji.get(sentiment, '🟡')} {sentiment.upper()}",
                )
            with col2:
                st.metric("감성 점수", f"{score:.2f}")

            st.markdown("### 주요 이벤트")
            for event in analysis.get("key_events", []):
                severity_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                st.markdown(
                    f"- {severity_color.get(event.get('severity', 'low'), '⚪')} "
                    f"**{event.get('event', '')}** "
                    f"(영향: {event.get('impact', 'neutral')}, "
                    f"관련: {', '.join(event.get('affected_tickers', []))})"
                )

            st.markdown("### 종합 요약")
            st.write(analysis.get("summary", ""))


# === Tab 4: 매수 가이드 ===
with tab4:
    holdings = pm.get_all_holdings()

    if not holdings:
        st.info("포트폴리오에 종목을 추가하고 최적화를 실행하세요.")
    elif "optimization_result" not in st.session_state:
        st.info("먼저 '최적화 결과' 탭에서 최적화를 실행하세요.")
    else:
        result = st.session_state["optimization_result"]

        st.subheader(f"예산 {budget:,.0f}원 매수 가이드")

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

                agent = PortfolioManagerAgent()
                portfolio_summary = pm.get_portfolio_summary()
                news_analysis = st.session_state.get("news_analysis", {})

                with st.spinner("AI 리포트 생성 중..."):
                    report = agent.generate_recommendation(
                        current_portfolio=portfolio_summary,
                        optimization_result=result,
                        news_analysis=news_analysis,
                        macro_data={},
                        budget=budget,
                    )

                st.session_state["ai_report"] = report
            except ValueError as e:
                st.error(str(e))

        if "ai_report" in st.session_state:
            st.markdown("### AI 투자 추천 리포트")
            st.markdown(st.session_state["ai_report"])

        st.divider()
        st.caption(DISCLAIMER)
