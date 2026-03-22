import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from db.database import init_db
from db.models import Holding, Transaction
from portfolio.manager import PortfolioManager
from portfolio.allocator import BudgetAllocator
from portfolio.tracker import PortfolioTracker
from data.fetcher import StockDataFetcher
from data.market_data import MarketDataProcessor
from data.news_fetcher import NewsFetcher
from utils.constants import RISK_LEVELS, DISCLAIMER
from utils.fx import get_usd_krw_rate, convert_to_krw
from analysis.technical import TechnicalAnalyzer

# --- 초기 설정 ---
st.set_page_config(page_title="주식 포트폴리오 에이전트", layout="wide")
init_db()

pm = PortfolioManager()
fetcher = StockDataFetcher()
market_proc = MarketDataProcessor()
news_fetcher = NewsFetcher()
tracker = PortfolioTracker()


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
        options=["최대 샤프 비율", "최소 변동성", "Black-Litterman"],
        index=0,
    )

    st.divider()

    # 종목 검색
    st.subheader("종목 검색")
    search_query = st.text_input("종목명 또는 티커 검색", placeholder="삼성전자, TIGER, AAPL 등")
    if search_query:
        import yfinance as yf
        search_results = []

        # 한국 ETF/주식 주요 목록에서 검색
        KR_STOCK_MAP = {
            "005930": "삼성전자", "000660": "SK하이닉스", "373220": "LG에너지솔루션",
            "207940": "삼성바이오로직스", "005380": "현대자동차", "000270": "기아",
            "068270": "셀트리온", "035420": "NAVER", "035720": "카카오",
            "051910": "LG화학", "006400": "삼성SDI", "105560": "KB금융",
            "055550": "신한지주", "066570": "LG전자", "028260": "삼성물산",
            "133690": "TIGER 미국나스닥100", "360750": "TIGER 미국S&P500",
            "381170": "TIGER 미국나스닥100커버드콜(합성)", "379800": "TIGER 미국S&P500TR(H)",
            "381180": "TIGER 미국테크TOP10 INDXX", "143850": "TIGER 미국S&P500선물(H)",
            "395160": "TIGER 미국배당+7%프리미엄다우존스", "458730": "TIGER 미국S&P500동일가중",
            "473460": "TIGER 미국나스닥100+15%프리미엄초단기",
            "069500": "KODEX 200", "229200": "KODEX 코스닥150",
            "305720": "KODEX 2차전지산업", "364690": "KODEX 나스닥100TR",
            "379810": "KODEX 미국S&P500TR", "461500": "KODEX 미국배당다우존스",
            "252670": "KODEX 200선물인버스2X", "122630": "KODEX 레버리지",
            "304660": "KODEX 미국채울트라30년선물(H)",
            "411060": "ACE 미국나스닥100", "360200": "ACE 미국S&P500",
        }

        q = search_query.upper()
        for ticker, name in KR_STOCK_MAP.items():
            if q in name.upper() or q in ticker:
                is_etf = any(tag in name for tag in ["TIGER", "KODEX", "ACE", "ARIRANG", "KBSTAR"])
                search_results.append({"티커": ticker, "종목명": name, "시장": "KR", "유형": "ETF" if is_etf else "주식"})

        # 미국 종목 yfinance 검색
        if len(search_results) == 0 and len(search_query) <= 6:
            try:
                t = yf.Ticker(search_query.upper())
                info = t.info
                if info.get("shortName"):
                    search_results.append({
                        "티커": search_query.upper(),
                        "종목명": info.get("shortName", ""),
                        "시장": "US" if info.get("quoteType") != "ETF" else "ETF",
                        "유형": info.get("quoteType", ""),
                    })
            except Exception:
                pass

        if search_results:
            st.dataframe(pd.DataFrame(search_results), use_container_width=True, hide_index=True)
            st.caption("위 결과를 참고하여 아래 폼에 입력하세요")
        elif search_query:
            st.caption("검색 결과가 없습니다")

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

    # 거래내역 업로드 (CSV/Excel)
    st.subheader("거래내역 가져오기")
    st.caption("증권사 앱에서 다운로드한 거래내역 파일을 업로드하세요")

    upload_broker = st.selectbox(
        "증권사 선택",
        ["신한투자증권", "KB증권", "범용 (직접입력)"],
        key="upload_broker",
    )
    uploaded_file = st.file_uploader(
        "CSV 또는 Excel 파일",
        type=["csv", "xlsx", "xls"],
        key="tx_upload",
    )

    if uploaded_file is not None:
        try:
            from broker.csv_parser import BrokerCSVParser
            from broker.aggregator import TransactionAggregator

            parser = BrokerCSVParser()
            file_data = uploaded_file.read()
            transactions = parser.parse(file_data, uploaded_file.name, upload_broker)

            if not transactions:
                st.warning("파싱된 거래 내역이 없습니다. 파일 형식을 확인하세요.")
            else:
                st.success(f"{len(transactions)}건의 거래 내역 파싱 완료")

                # 거래 내역 미리보기
                with st.expander(f"거래 내역 미리보기 ({len(transactions)}건)"):
                    tx_df = pd.DataFrame(transactions)
                    st.dataframe(tx_df, use_container_width=True, hide_index=True)

                # 집계 결과
                aggregator = TransactionAggregator()
                holdings_summary = aggregator.aggregate(transactions)

                st.markdown("**집계 결과 (현재 보유 종목)**")
                summary_rows = []
                for h in holdings_summary:
                    summary_rows.append({
                        "종목명": h["name"],
                        "티커": h["ticker"],
                        "보유수량": h["quantity"],
                        "평균매입가": f"{h['avg_price']:,.0f}",
                        "총매입금액": f"{h['total_cost']:,.0f}",
                        "매수횟수": h["buy_count"],
                        "최초매수": h["first_buy_date"],
                        "최근매수": h["last_buy_date"],
                    })
                st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

                # 포트폴리오에 반영
                if st.button("포트폴리오에 반영", type="primary"):
                    added = 0
                    for h in holdings_summary:
                        ticker = h["ticker"]
                        # 6자리 숫자면 한국 종목
                        is_kr = ticker.isdigit() and len(ticker) == 6
                        # ETF 키워드 체크
                        etf_keywords = ["TIGER", "KODEX", "ACE", "ARIRANG", "KBSTAR", "SOL", "HANARO"]
                        is_etf = any(kw in h["name"] for kw in etf_keywords)

                        if is_kr:
                            market = "KR"
                            currency = "KRW"
                        elif is_etf and not is_kr:
                            market = "ETF"
                            currency = "USD"
                        else:
                            market = "US"
                            currency = "USD"

                        holding = Holding(
                            ticker=ticker,
                            market=market,
                            name=h["name"],
                            quantity=h["quantity"],
                            avg_price=h["avg_price"],
                            currency=currency,
                        )
                        pm.add_holding(holding)
                        added += 1

                    st.success(f"{added}개 종목이 포트폴리오에 추가되었습니다!")
                    st.rerun()

        except Exception as e:
            st.error(f"파일 처리 실패: {e}")

    # CSV 템플릿 다운로드
    with st.expander("CSV 템플릿 다운로드"):
        st.caption("증권사 파일이 없다면 이 템플릿을 사용하세요")
        try:
            from broker.csv_parser import BrokerCSVParser
            template = BrokerCSVParser.generate_template()
            csv_data = template.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "템플릿 다운로드 (CSV)",
                data=csv_data,
                file_name="거래내역_템플릿.csv",
                mime="text/csv",
            )
        except Exception:
            pass

    st.divider()

    # 환율 정보 표시
    try:
        fx_rate = get_usd_krw_rate()
        st.metric("USD/KRW 환율", f"{fx_rate:,.0f}")
    except Exception:
        st.caption("환율 정보 로딩 실패")

    st.caption(DISCLAIMER)


# --- 메인 영역 ---
st.title("주식 포트폴리오 에이전트")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["포트폴리오 현황", "최적화 결과", "뉴스 & 시장 분석", "매수 가이드", "기술적 분석", "백테스팅", "AI 토론"]
)


# === 공통 유틸 ===
def load_portfolio_data():
    """포트폴리오 데이터를 로드하고 현재가/환율을 적용한 DataFrame 반환"""
    holdings = pm.get_all_holdings()
    if not holdings:
        return holdings, pd.DataFrame()

    fx_rate = get_usd_krw_rate()
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

        price = current_price or h.avg_price
        total_cost = h.avg_price * h.quantity
        total_value = price * h.quantity

        # KRW 환산
        if h.currency == "USD":
            total_cost_krw = total_cost * fx_rate
            total_value_krw = total_value * fx_rate
        else:
            total_cost_krw = total_cost
            total_value_krw = total_value

        pnl_krw = total_value_krw - total_cost_krw
        pnl_pct = (pnl_krw / total_cost_krw * 100) if total_cost_krw > 0 else 0

        rows.append({
            "ID": h.id,
            "종목명": h.name,
            "티커": h.ticker,
            "시장": h.market,
            "수량": h.quantity,
            "평균매입가": h.avg_price,
            "현재가": price,
            "통화": h.currency,
            "평가금액(원)": total_value_krw,
            "매입금액(원)": total_cost_krw,
            "손익(원)": pnl_krw,
            "수익률(%)": round(pnl_pct, 2),
            "섹터": h.sector or "N/A",
        })

    return holdings, pd.DataFrame(rows)


# === Tab 1: 포트폴리오 현황 ===
with tab1:
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


# === Tab 2: 최적화 결과 ===
with tab2:
    holdings = pm.get_all_holdings()

    if len(holdings) < 2:
        st.info("최적화를 실행하려면 최소 2개 이상의 종목이 필요합니다.")
    else:
        if st.button("최적화 실행", type="primary"):
            tickers = [{"ticker": h.ticker, "market": h.market} for h in holdings]
            allocator = BudgetAllocator()

            strat_map = {
                "최대 샤프 비율": "max_sharpe",
                "최소 변동성": "min_volatility",
                "Black-Litterman": "black_litterman",
            }
            strat = strat_map.get(strategy, "max_sharpe")

            with st.spinner("포트폴리오 최적화 중..."):
                if strat == "black_litterman":
                    # BL: 뉴스 분석 기반 뷰 생성 후 최적화
                    try:
                        from agent.views_generator import ViewsGeneratorAgent
                        views_agent = ViewsGeneratorAgent()
                        news_analysis = st.session_state.get("news_analysis", {})
                        ticker_list = [h.ticker for h in holdings]
                        views_result = views_agent.generate_views(
                            ticker_list, news_analysis, {}
                        )
                        st.session_state["bl_views"] = views_result

                        # 가격 데이터로 옵티마이저 생성 후 BL 최적화
                        from portfolio.optimizer import PortfolioOptimizer
                        prices = fetcher.get_multiple_prices(tickers, "1y")
                        if prices.empty or len(prices.columns) < 2:
                            st.error("최소 2개 이상의 종목 시세 데이터가 필요합니다.")
                        else:
                            optimizer = PortfolioOptimizer(prices)
                            opt_result = optimizer.optimize_black_litterman(
                                views=views_result.get("views", {}),
                                confidence=views_result.get("confidence"),
                            )
                            active_weights = {k: v for k, v in opt_result.weights.items() if v > 0.001}
                            alloc = optimizer.calculate_discrete_allocation(active_weights, budget)
                            result = {
                                "strategy": opt_result.strategy,
                                "optimal_weights": active_weights,
                                "expected_return": opt_result.expected_return,
                                "volatility": opt_result.volatility,
                                "sharpe_ratio": opt_result.sharpe_ratio,
                                "buy_guide": alloc["allocation"],
                                "invested": alloc["invested"],
                                "leftover": alloc["leftover"],
                            }
                            st.session_state["optimization_result"] = result
                    except Exception as e:
                        st.error(f"Black-Litterman 최적화 실패: {e}")
                else:
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

            # 전략 표시
            strat_names = {
                "max_sharpe": "최대 샤프 비율",
                "min_volatility": "최소 변동성",
                "black_litterman": "Black-Litterman",
            }
            st.caption(f"전략: {strat_names.get(result.get('strategy', ''), result.get('strategy', ''))}")

            # BL 뷰 표시
            if "bl_views" in st.session_state and result.get("strategy") == "black_litterman":
                with st.expander("AI 생성 투자 뷰 (Black-Litterman)"):
                    bl = st.session_state["bl_views"]
                    st.json(bl.get("views", {}))
                    st.caption(bl.get("reasoning", ""))

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

            # 효율적 프론티어
            try:
                tickers_data = [{"ticker": h.ticker, "market": h.market} for h in pm.get_all_holdings()]
                prices = fetcher.get_multiple_prices(tickers_data, "1y")
                if not prices.empty and len(prices.columns) >= 2:
                    from portfolio.optimizer import PortfolioOptimizer
                    opt = PortfolioOptimizer(prices)
                    ef_data = opt.get_efficient_frontier_data(n_points=30)
                    if ef_data:
                        st.subheader("효율적 프론티어")
                        ef_df = pd.DataFrame(ef_data)
                        fig_ef = go.Figure()
                        fig_ef.add_trace(go.Scatter(
                            x=ef_df["volatility"], y=ef_df["return"],
                            mode="lines", name="효율적 프론티어",
                            line=dict(color="blue"),
                        ))
                        # 현재 최적 포트폴리오 위치 표시
                        fig_ef.add_trace(go.Scatter(
                            x=[result["volatility"]], y=[result["expected_return"]],
                            mode="markers", name="최적 포트폴리오",
                            marker=dict(size=12, color="red", symbol="star"),
                        ))
                        fig_ef.update_layout(
                            xaxis_title="변동성 (연율화)",
                            yaxis_title="기대수익률 (연율화)",
                            xaxis_tickformat=".1%",
                            yaxis_tickformat=".1%",
                        )
                        st.plotly_chart(fig_ef, use_container_width=True)
            except Exception:
                pass


# === Tab 3: 뉴스 & 시장 분석 ===
with tab3:
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


# === Tab 5: 기술적 분석 ===
with tab5:
    holdings = pm.get_all_holdings()

    if not holdings:
        st.info("포트폴리오에 종목을 추가하세요.")
    else:
        selected_ticker = st.selectbox(
            "분석할 종목 선택",
            options=[(h.ticker, h.market, f"{h.name} ({h.ticker})") for h in holdings],
            format_func=lambda x: x[2],
        )

        if selected_ticker:
            ticker, market, label = selected_ticker
            period = st.selectbox("분석 기간", ["6mo", "1y", "2y"], index=1)

            try:
                price_df = fetcher.get_price_data(ticker, market, period=period)
                if price_df.empty:
                    st.warning(f"{ticker}의 시세 데이터를 가져올 수 없습니다.")
                else:
                    close_col = "Close" if "Close" in price_df.columns else "종가"
                    prices = price_df[close_col]

                    # 기술적 지표 계산
                    ta = TechnicalAnalyzer()
                    signal = ta.get_signal_summary(prices)

                    # 신호 요약
                    st.subheader(f"{label} 기술적 분석")
                    signal_colors = {"매수 우위": "green", "매도 우위": "red", "중립": "orange"}
                    st.markdown(
                        f"**종합 신호**: :{signal_colors.get(signal['signal'], 'gray')}[{signal['signal']}]"
                    )

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("RSI(14)", f"{signal.get('rsi', 'N/A')}")
                    col2.metric("MACD", f"{signal.get('macd', 'N/A')}")
                    col3.metric("BB 위치", signal.get("bb_position", "N/A"))
                    col4.metric("MA20 대비", signal.get("price_vs_ma20", "N/A"))

                    # 가격 + 볼린저밴드 차트
                    bb = ta.bollinger_bands(prices)
                    ma = ta.moving_averages(prices)

                    fig = make_subplots(
                        rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.05,
                        row_heights=[0.5, 0.25, 0.25],
                        subplot_titles=["가격 & 볼린저밴드", "RSI", "MACD"],
                    )

                    # 가격 + BB
                    fig.add_trace(go.Scatter(x=prices.index, y=prices, name="종가", line=dict(color="black")), row=1, col=1)
                    fig.add_trace(go.Scatter(x=prices.index, y=bb["upper"], name="BB 상단", line=dict(color="gray", dash="dash")), row=1, col=1)
                    fig.add_trace(go.Scatter(x=prices.index, y=bb["lower"], name="BB 하단", line=dict(color="gray", dash="dash"), fill="tonexty", fillcolor="rgba(200,200,200,0.1)"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=prices.index, y=ma["MA20"], name="MA20", line=dict(color="orange")), row=1, col=1)
                    fig.add_trace(go.Scatter(x=prices.index, y=ma["MA60"], name="MA60", line=dict(color="blue")), row=1, col=1)

                    # RSI
                    rsi_data = ta.rsi(prices)
                    fig.add_trace(go.Scatter(x=rsi_data.index, y=rsi_data, name="RSI", line=dict(color="purple")), row=2, col=1)
                    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

                    # MACD
                    macd_data = ta.macd(prices)
                    fig.add_trace(go.Scatter(x=prices.index, y=macd_data["macd"], name="MACD", line=dict(color="blue")), row=3, col=1)
                    fig.add_trace(go.Scatter(x=prices.index, y=macd_data["signal"], name="Signal", line=dict(color="orange")), row=3, col=1)
                    fig.add_trace(go.Bar(x=prices.index, y=macd_data["histogram"], name="Histogram", marker_color="gray"), row=3, col=1)

                    fig.update_layout(height=800, showlegend=True, hovermode="x unified")
                    st.plotly_chart(fig, use_container_width=True)

                    # 신호 상세
                    with st.expander("상세 기술적 신호"):
                        for s in signal.get("details", []):
                            st.markdown(f"- {s}")

            except Exception as e:
                st.error(f"기술적 분석 실패: {e}")

        # 펀더멘탈 분석 (US/ETF 종목만)
        us_holdings = [h for h in holdings if h.market in ("US", "ETF")]
        if us_holdings:
            st.divider()
            st.subheader("펀더멘탈 분석 (AI)")
            fa_ticker = st.selectbox(
                "분석할 종목 (US/ETF)",
                options=[(h.ticker, h.name) for h in us_holdings],
                format_func=lambda x: f"{x[1]} ({x[0]})",
                key="fa_ticker",
            )

            if fa_ticker and st.button("펀더멘탈 분석 실행"):
                try:
                    from agent.fundamental_analyst import FundamentalAnalystAgent

                    fa_agent = FundamentalAnalystAgent()
                    with st.spinner("재무 데이터 수집 중..."):
                        financials_data = fetcher.get_financials(fa_ticker[0], "US")
                        stock_info = market_proc.get_stock_info(fa_ticker[0], "US")

                    # DataFrame -> dict 변환
                    fin_dict = {}
                    for key, value in financials_data.items():
                        if isinstance(value, pd.DataFrame):
                            fin_dict[key] = value.to_dict()
                        else:
                            fin_dict[key] = value

                    with st.spinner("AI 펀더멘탈 분석 중 (qwen3.5:27b)..."):
                        fa_report = fa_agent.analyze(
                            fa_ticker[0], fa_ticker[1], fin_dict, stock_info
                        )
                    st.markdown(fa_report)
                except Exception as e:
                    st.error(f"펀더멘탈 분석 실패: {e}")


# === Tab 6: 백테스팅 ===
with tab6:
    holdings = pm.get_all_holdings()

    if len(holdings) < 2:
        st.info("백테스팅을 실행하려면 최소 2개 이상의 종목이 필요합니다.")
    else:
        st.subheader("전략 백테스팅")

        col1, col2, col3 = st.columns(3)
        with col1:
            bt_period = st.selectbox("데이터 기간", ["1y", "2y", "5y"], index=1, key="bt_period")
        with col2:
            bt_lookback = st.number_input("룩백 기간 (일)", value=252, min_value=60, max_value=504, key="bt_lookback")
        with col3:
            bt_rebalance = st.number_input("리밸런싱 주기 (일)", value=63, min_value=21, max_value=252, key="bt_rebalance")

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
                "equal_weight": "동일 비중",
            }
            perf_rows = []
            for r in results:
                if "error" in r:
                    continue
                perf_rows.append({
                    "전략": strat_names.get(r["strategy"], r["strategy"]),
                    "총 수익률": f"{r['total_return']:.2%}",
                    "연환산 수익률": f"{r['annualized_return']:.2%}",
                    "변동성": f"{r['volatility']:.2%}",
                    "샤프 비율": f"{r['sharpe_ratio']:.2f}",
                    "최대 낙폭": f"{r['max_drawdown']:.2%}",
                })
            if perf_rows:
                st.dataframe(pd.DataFrame(perf_rows), use_container_width=True, hide_index=True)

            # 자산 곡선 차트
            st.markdown("### 자산 곡선 (초기값 = 1)")
            fig_bt = go.Figure()
            colors = ["blue", "orange", "green"]
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
            st.plotly_chart(fig_bt, use_container_width=True)


# === Tab 7: AI 토론 ===
with tab7:
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
