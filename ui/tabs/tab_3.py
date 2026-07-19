import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json


def render(ctx):
    pm = ctx.pm
    news_fetcher = ctx.news_fetcher
    holdings = pm.get_all_holdings()
    tickers = [h.ticker for h in holdings]

    # --- 뉴스 분석 섹션 ---
    st.subheader("뉴스 분석")

    if not tickers:
        st.info("포트폴리오에 종목을 추가하면 뉴스 분석을 실행할 수 있습니다.")
    else:
        if st.button("뉴스 수집 & AI 분석 실행"):
            try:
                # 실제 뉴스 수집
                all_news = []
                with st.spinner("뉴스 수집 중..."):
                    for h in holdings[:5]:  # 최대 5개 종목
                        articles = news_fetcher.get_ticker_news(h.ticker, h.market, limit=3)
                        all_news.extend(articles)
                    # 시장 전반 뉴스
                    markets = set(h.market for h in holdings)
                    for m in markets:
                        market_news = news_fetcher.get_market_news(m, limit=3)
                        all_news.extend(market_news)

                if not all_news:
                    st.warning("뉴스를 수집하지 못했습니다. 네트워크 연결을 확인하세요.")
                else:
                    st.session_state["collected_news"] = all_news
                    # AI 감성 분석
                    from agent.news_analyzer import NewsAnalystAgent
                    agent = NewsAnalystAgent()
                    with st.spinner("AI 뉴스 분석 중 (llama3.1:8b)..."):
                        analysis = agent.analyze_news(all_news, tickers)
                    st.session_state["news_analysis"] = analysis

                    # 감성 히스토리 저장
                    try:
                        from db.database import get_connection
                        from datetime import date
                        conn = get_connection()
                        conn.execute(
                            """INSERT INTO sentiment_history
                               (date, market_sentiment, sentiment_score, ticker_sentiments_json, summary)
                               VALUES (?, ?, ?, ?, ?)""",
                            (
                                date.today().isoformat(),
                                analysis.get("market_sentiment"),
                                analysis.get("sentiment_score"),
                                json.dumps(analysis.get("ticker_sentiments", {}), ensure_ascii=False),
                                analysis.get("summary", ""),
                            ),
                        )
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
            except Exception as e:
                st.error(f"뉴스 분석 실패: {e}")

        # 수집된 뉴스 표시
        if "collected_news" in st.session_state:
            with st.expander(f"수집된 뉴스 ({len(st.session_state['collected_news'])}건)", expanded=False):
                for article in st.session_state["collected_news"]:
                    st.markdown(f"- **{article['title']}** ({article.get('source', '')}, {article.get('date', '')})")

        # AI 분석 결과
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

    # --- 감성 추이 차트 ---
    try:
        from db.database import get_connection as _get_conn
        _conn = _get_conn()
        sent_rows = _conn.execute(
            "SELECT date, sentiment_score FROM sentiment_history ORDER BY date ASC LIMIT 30"
        ).fetchall()
        _conn.close()
        if len(sent_rows) >= 2:
            st.divider()
            st.subheader("감성 점수 추이")
            sent_df = pd.DataFrame([dict(r) for r in sent_rows])
            fig_sent = go.Figure()
            fig_sent.add_trace(go.Scatter(
                x=sent_df["date"], y=sent_df["sentiment_score"],
                mode="lines+markers", name="감성 점수",
                line=dict(color="purple"),
            ))
            fig_sent.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_sent.update_layout(yaxis_title="감성 점수 (-1 ~ 1)", xaxis_title="날짜")
            st.plotly_chart(fig_sent, use_container_width=True)
    except Exception:
        pass

    # --- 거시경제 지표 섹션 ---
    st.divider()
    st.subheader("거시경제 지표")

    if st.button("경제지표 조회"):
        try:
            from data.economic_data import EconomicDataFetcher
            econ = EconomicDataFetcher()
            with st.spinner("경제지표 수집 중..."):
                macro_summary = econ.get_macro_summary()
            st.session_state["macro_data"] = macro_summary
        except ValueError as e:
            st.error(f"FRED API 키가 필요합니다: {e}")
        except Exception as e:
            st.error(f"경제지표 조회 실패: {e}")

    if "macro_data" in st.session_state:
        macro = st.session_state["macro_data"]
        if macro:
            cols = st.columns(3)
            for i, (name, data) in enumerate(macro.items()):
                with cols[i % 3]:
                    latest = data.get("latest", 0)
                    change = data.get("change_1m")
                    delta_str = f"{change:+.2f}" if change is not None else None
                    st.metric(name, f"{latest:.2f}", delta=delta_str)
