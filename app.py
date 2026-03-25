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
from utils.constants import RISK_LEVELS, DISCLAIMER, KR_STOCK_MAP
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

    default_budget = st.session_state.get("invest_budget", 1_000_000)
    budget = st.number_input(
        "추가 투자 예산 (원)", value=default_budget, step=100_000, format="%d", key="budget_input"
    )
    risk_level = st.select_slider(
        "위험 선호도",
        options=list(RISK_LEVELS.keys()),
        value="중립",
    )
    strategy = st.radio(
        "최적화 전략",
        options=["최대 샤프 비율", "최소 변동성", "Black-Litterman", "HRP (계층적 리스크 패리티)", "최소 CVaR (꼬리 위험)"],
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

    # 거래내역 업로드 (CSV/Excel) - 개선된 버전
    st.subheader("거래내역 가져오기")
    st.caption("증권사 앱에서 다운로드한 거래내역 파일을 업로드하세요")

    # 마지막 업로드 정보
    last_upload = pm.get_last_upload_info()
    if last_upload:
        st.caption(f"최근 업로드: {last_upload.get('created_at', '')[:16]} ({last_upload.get('inserted_transactions', 0)}건)")

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

            # 자동 감지
            detected_broker = BrokerCSVParser.detect_broker(file_data, uploaded_file.name)
            st.info(f"감지된 증권사: **{detected_broker}**")

            transactions = parser.parse(file_data, uploaded_file.name, detected_broker)

            if not transactions:
                st.warning("파싱된 거래 내역이 없습니다. 파일 형식을 확인하세요.")
            else:
                # 거래내역 DB 저장 (중복 필터링)
                inserted, skipped = pm.record_transactions_batch(transactions)
                if skipped > 0:
                    st.info(f"{len(transactions)}건 중 {inserted}건 신규 반영, {skipped}건 중복 제외")
                else:
                    st.success(f"{inserted}건 거래내역 저장 완료")

                with st.expander(f"거래 내역 미리보기 ({len(transactions)}건)"):
                    tx_df = pd.DataFrame(transactions)
                    st.dataframe(tx_df, use_container_width=True, hide_index=True)

                # 기존 보유종목과 병합
                aggregator = TransactionAggregator()
                holdings_summary = aggregator.aggregate(transactions)
                existing_holdings = pm.get_all_holdings()
                merge_plan = aggregator.merge_with_existing(holdings_summary, existing_holdings)

                st.markdown("**반영 계획**")
                plan_rows = []
                for m in merge_plan:
                    action_label = "업데이트 (기존 종목 합산)" if m["action"] == "update" else "신규 추가"
                    plan_rows.append({
                        "종목명": m["name"],
                        "티커": m["ticker"],
                        "수량": m["quantity"],
                        "평균매입가": f"{m['avg_price']:,.0f}",
                        "반영방식": action_label,
                    })
                st.dataframe(pd.DataFrame(plan_rows), use_container_width=True, hide_index=True)

                if st.button("포트폴리오에 반영", type="primary"):
                    added, updated = 0, 0
                    for m in merge_plan:
                        ticker = m["ticker"]
                        is_kr = ticker.isdigit() and len(ticker) == 6
                        etf_keywords = ["TIGER", "KODEX", "ACE", "ARIRANG", "KBSTAR", "SOL", "HANARO"]
                        is_etf = any(kw in m["name"] for kw in etf_keywords)
                        market = "KR" if is_kr else ("ETF" if is_etf else "US")
                        currency = "KRW" if is_kr else "USD"

                        if m["action"] == "update" and m["existing_id"]:
                            pm.update_or_merge_holding(m["existing_id"], m["quantity"], m["avg_price"])
                            updated += 1
                        else:
                            holding = Holding(
                                ticker=ticker, market=market, name=m["name"],
                                quantity=m["quantity"], avg_price=m["avg_price"], currency=currency,
                            )
                            pm.add_holding(holding)
                            added += 1

                    pm.record_upload_history(
                        uploaded_file.name, detected_broker,
                        len(transactions), inserted, skipped,
                    )
                    msg = []
                    if added: msg.append(f"{added}개 신규 추가")
                    if updated: msg.append(f"{updated}개 기존 종목 업데이트")
                    st.success(", ".join(msg) + " 완료!")
                    st.rerun()

        except Exception as e:
            st.error(f"파일 처리 실패: {e}")

    with st.expander("CSV 템플릿 다운로드"):
        st.caption("증권사 파일이 없다면 이 템플릿을 사용하세요")
        try:
            from broker.csv_parser import BrokerCSVParser
            template = BrokerCSVParser.generate_template()
            csv_data = template.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "템플릿 다운로드 (CSV)",
                data=csv_data, file_name="거래내역_템플릿.csv", mime="text/csv",
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

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs(
    ["포트폴리오 현황", "최적화 결과", "뉴스 & 시장 분석", "매수 가이드", "기술적 분석", "백테스팅", "AI 토론", "가계부", "종목 스크리너", "목표 시뮬레이션", "관심종목"]
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
                "HRP (계층적 리스크 패리티)": "hrp",
                "최소 CVaR (꼬리 위험)": "min_cvar",
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
            is_cvar = result.get("strategy") == "min_cvar"
            col2.metric("CVaR (5%)" if is_cvar else "변동성", f"{result['volatility']:.2%}")
            col3.metric("수익률/CVaR" if is_cvar else "샤프 비율", f"{result['sharpe_ratio']:.2f}")

            # 전략 표시
            strat_names = {
                "max_sharpe": "최대 샤프 비율",
                "min_volatility": "최소 변동성",
                "black_litterman": "Black-Litterman",
                "hrp": "HRP (계층적 리스크 패리티)",
                "min_cvar": "최소 CVaR (꼬리 위험)",
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

            # 리스크 기여도 분석
            try:
                active_weights = result.get("optimal_weights", {})
                if active_weights and len(active_weights) >= 2:
                    tickers_data = [{"ticker": h.ticker, "market": h.market} for h in pm.get_all_holdings()]
                    prices = fetcher.get_multiple_prices(tickers_data, "1y")
                    if not prices.empty:
                        from portfolio.optimizer import PortfolioOptimizer
                        opt_rc = PortfolioOptimizer(prices)
                        risk_contrib = opt_rc.calculate_risk_contribution(active_weights)
                        if risk_contrib:
                            st.subheader("리스크 기여도")
                            rc_df = pd.DataFrame(
                                list(risk_contrib.items()),
                                columns=["종목", "리스크 기여도"],
                            ).sort_values("리스크 기여도", ascending=True)
                            fig_rc = px.bar(
                                rc_df, x="리스크 기여도", y="종목",
                                orientation="h", title="종목별 포트폴리오 리스크 기여도",
                            )
                            fig_rc.update_layout(xaxis_tickformat=".1%")
                            st.plotly_chart(fig_rc, use_container_width=True)
                            st.caption("각 종목이 전체 포트폴리오 리스크에 기여하는 비율입니다.")
            except Exception:
                pass

            # 리밸런싱 목표 비중 설정
            if st.button("이 비중을 리밸런싱 목표로 설정", key="set_rebalance_target"):
                from portfolio.rebalancer import Rebalancer
                rebalancer = Rebalancer()
                rebalancer.save_targets(result["optimal_weights"], result.get("strategy", ""))
                st.success("목표 비중이 설정되었습니다. 포트폴리오 현황 탭에서 드리프트 알림을 확인할 수 있습니다.")


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

    # 종목 간 상관관계 히트맵
    if len(holdings) >= 2:
        st.divider()
        st.subheader("종목 간 상관관계")
        try:
            corr_tickers = [{"ticker": h.ticker, "market": h.market} for h in holdings]
            corr_prices = fetcher.get_multiple_prices(corr_tickers, "1y")
            if not corr_prices.empty and len(corr_prices.columns) >= 2:
                corr_matrix = market_proc.calculate_correlation(corr_prices)
                # 티커 → 종목명 매핑
                name_map = {h.ticker: h.name for h in holdings}
                corr_labels = [name_map.get(t, t) for t in corr_matrix.columns]
                fig_corr = px.imshow(
                    corr_matrix.values,
                    x=corr_labels, y=corr_labels,
                    color_continuous_scale="RdBu_r",
                    zmin=-1, zmax=1,
                    text_auto=".2f",
                    title="수익률 상관관계 매트릭스",
                )
                fig_corr.update_layout(height=500)
                st.plotly_chart(fig_corr, use_container_width=True)
                st.caption("해석: >0.7 높은 상관관계 (분산 효과 낮음) | <0.3 낮은 상관관계 (분산 효과 높음)")
        except Exception as e:
            st.error(f"상관관계 분석 실패: {e}")


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


# === Tab 8: 가계부 ===
with tab8:
    from datetime import date as _date

    # 가계부 초기화
    try:
        from db.database import init_budget_defaults
        init_budget_defaults()
    except Exception:
        pass

    from budget.manager import BudgetManager
    from budget.models import BudgetEntry
    bm = BudgetManager()

    current_ym = _date.today().strftime("%Y-%m")

    btab1, btab2, btab3, btab4, btab5, btab6 = st.tabs(
        ["수입/지출 입력", "월별 현황", "트렌드 분석", "예산 설정", "AI 분석", "투자 연계"]
    )

    # --- 가계부 Sub-tab 1: 수입/지출 입력 ---
    with btab1:
        st.subheader("수입/지출 입력")

        col_form, col_csv = st.columns(2)

        with col_form:
            st.markdown("**수동 입력**")
            with st.form("budget_entry_form"):
                be_date = st.date_input("날짜", value=_date.today())
                be_type = st.radio("구분", ["지출", "수입"], horizontal=True)
                entry_type = "expense" if be_type == "지출" else "income"

                categories = bm.get_categories(entry_type)
                cat_options = [f"{c.icon} {c.name}" if c.icon else c.name for c in categories]
                cat_names = [c.name for c in categories]
                be_category = st.selectbox("카테고리", cat_options)
                be_amount = st.number_input("금액 (원)", min_value=0, value=0, step=1000)
                be_desc = st.text_input("내용", placeholder="점심 식사, 월급 등")
                be_submitted = st.form_submit_button("입력")

                if be_submitted and be_amount > 0:
                    # 아이콘 제거하고 카테고리명만 추출
                    cat_idx = cat_options.index(be_category) if be_category in cat_options else 0
                    cat_name = cat_names[cat_idx] if cat_idx < len(cat_names) else be_category
                    entry = BudgetEntry(
                        date=be_date.isoformat(),
                        amount=be_amount,
                        type=entry_type,
                        category=cat_name,
                        description=be_desc,
                    )
                    bm.add_entry(entry)
                    st.success(f"{be_type} {be_amount:,}원 입력 완료!")
                    st.rerun()

        with col_csv:
            st.markdown("**은행/카드 CSV 업로드**")
            bank_file = st.file_uploader("CSV/Excel 파일", type=["csv", "xlsx", "xls"], key="bank_csv")

            if bank_file is not None:
                try:
                    from budget.csv_parser import BankCSVParser
                    bank_parser = BankCSVParser()
                    bank_data = bank_file.read()
                    detected_bank = BankCSVParser.detect_bank(bank_data, bank_file.name)
                    st.info(f"감지된 은행/카드: **{detected_bank}**")

                    bank_entries = bank_parser.parse(bank_data, bank_file.name, detected_bank)
                    if bank_entries:
                        st.success(f"{len(bank_entries)}건 파싱 완료")
                        with st.expander("미리보기"):
                            st.dataframe(pd.DataFrame(bank_entries), use_container_width=True, hide_index=True)

                        if st.button("가계부에 반영", key="apply_bank_csv"):
                            count = bm.add_entries_batch(bank_entries)
                            st.success(f"{count}건 입력 완료!")
                            st.rerun()
                    else:
                        st.warning("파싱된 내역이 없습니다.")
                except Exception as e:
                    st.error(f"파일 처리 실패: {e}")

        # 최근 내역
        st.divider()
        st.subheader("최근 입력 내역")
        recent = bm.get_entries(limit=20)
        if recent:
            recent_rows = []
            for e in recent:
                recent_rows.append({
                    "ID": e.id,
                    "날짜": e.date,
                    "구분": "수입" if e.type == "income" else "지출",
                    "카테고리": e.category,
                    "금액": f"{e.amount:,.0f}원",
                    "내용": e.description or "",
                    "출처": e.source,
                })
            st.dataframe(pd.DataFrame(recent_rows).drop(columns=["ID"]), use_container_width=True, hide_index=True)

            del_id = st.number_input("삭제할 항목 ID", min_value=0, value=0, key="del_budget_id")
            if st.button("항목 삭제", key="del_budget_btn") and del_id > 0:
                bm.delete_entry(del_id)
                st.success("삭제 완료!")
                st.rerun()
        else:
            st.info("입력된 내역이 없습니다.")

    # --- 가계부 Sub-tab 2: 월별 현황 ---
    with btab2:
        from budget.analyzer import BudgetAnalyzer
        ba = BudgetAnalyzer()

        sel_month = st.text_input("조회 월 (YYYY-MM)", value=current_ym, key="budget_month")
        summary = ba.get_monthly_summary(sel_month)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("수입", f"{summary.total_income:,.0f}원")
        col2.metric("지출", f"{summary.total_expense:,.0f}원")
        col3.metric("저축", f"{summary.savings:,.0f}원")
        col4.metric("저축률", f"{summary.savings_rate:.1f}%")

        # 카테고리별 지출
        cat_df = ba.get_category_breakdown(sel_month)
        if not cat_df.empty:
            col_a, col_b = st.columns(2)
            with col_a:
                fig_cat = px.pie(cat_df, names="category", values="amount", title="카테고리별 지출 비중")
                st.plotly_chart(fig_cat, use_container_width=True)
            with col_b:
                fig_bar = px.bar(cat_df, x="category", y="amount", title="카테고리별 지출 금액")
                st.plotly_chart(fig_bar, use_container_width=True)

        # 예산 초과 알림
        alerts = bm.get_budget_alerts(sel_month)
        if alerts:
            st.warning("예산 초과/임박 카테고리:")
            for a in alerts:
                pct = a["pct"]
                color = "🔴" if pct >= 100 else "🟡"
                st.markdown(f"- {color} **{a['category']}**: {a['spent']:,.0f}원 / {a['limit']:,.0f}원 ({pct:.0f}%)")

    # --- 가계부 Sub-tab 3: 트렌드 분석 ---
    with btab3:
        from budget.analyzer import BudgetAnalyzer
        ba3 = BudgetAnalyzer()

        trend = ba3.get_monthly_trend(12)
        if not trend.empty and len(trend) >= 2:
            st.subheader("수입 vs 지출 추이 (12개월)")
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(x=trend["year_month"], y=trend["total_income"], name="수입", marker_color="blue"))
            fig_trend.add_trace(go.Bar(x=trend["year_month"], y=trend["total_expense"], name="지출", marker_color="red"))
            fig_trend.update_layout(barmode="group", xaxis_title="월", yaxis_title="금액 (원)")
            st.plotly_chart(fig_trend, use_container_width=True)

            st.subheader("저축률 추이")
            fig_sav = go.Figure()
            fig_sav.add_trace(go.Scatter(
                x=trend["year_month"], y=trend["savings_rate"],
                mode="lines+markers", name="저축률 (%)", line=dict(color="green"),
            ))
            fig_sav.add_hline(y=30, line_dash="dash", line_color="orange", annotation_text="목표 30%")
            fig_sav.update_layout(yaxis_title="저축률 (%)")
            st.plotly_chart(fig_sav, use_container_width=True)
        else:
            st.info("2개월 이상의 데이터가 필요합니다.")

    # --- 가계부 Sub-tab 4: 예산 설정 ---
    with btab4:
        st.subheader("카테고리별 월 예산 설정")

        expense_cats = bm.get_categories("expense")
        for cat in expense_cats:
            col1, col2 = st.columns([3, 1])
            with col1:
                label = f"{cat.icon} {cat.name}" if cat.icon else cat.name
                new_limit = st.number_input(
                    label, value=int(cat.budget_limit or 0),
                    min_value=0, step=10000, key=f"budget_{cat.name}",
                )
            with col2:
                if st.button("저장", key=f"save_{cat.name}"):
                    bm.update_category_budget(cat.name, new_limit)
                    st.success(f"{cat.name} 예산 설정: {new_limit:,}원")

        # 커스텀 카테고리 추가
        st.divider()
        st.subheader("카테고리 추가")
        with st.form("add_cat_form"):
            new_cat_name = st.text_input("카테고리명")
            new_cat_type = st.selectbox("구분", ["expense", "income"])
            new_cat_icon = st.text_input("아이콘 (이모지)", placeholder="🍕")
            if st.form_submit_button("추가") and new_cat_name:
                from budget.models import BudgetCategory
                bm.add_category(BudgetCategory(name=new_cat_name, type=new_cat_type, icon=new_cat_icon))
                st.success(f"카테고리 '{new_cat_name}' 추가 완료!")
                st.rerun()

        # 고정지출 관리
        st.divider()
        st.subheader("고정지출/수입 관리")

        from budget.recurring import RecurringExpenseManager
        rem = RecurringExpenseManager()

        recurring_items = rem.get_recurring_items()
        if recurring_items:
            for item in recurring_items:
                type_label = "수입" if item.type == "income" else "지출"
                st.markdown(f"- **{item.category}**: {item.amount:,.0f}원 ({type_label}, 매월 {item.recurring_day or 1}일) — {item.description or ''}")
        else:
            st.caption("등록된 고정지출/수입이 없습니다.")

        with st.form("add_recurring_form"):
            st.markdown("**고정지출/수입 등록**")
            rc_type = st.radio("구분", ["지출", "수입"], horizontal=True, key="rc_type")
            rc_category = st.text_input("카테고리", placeholder="주거/관리비", key="rc_cat")
            rc_amount = st.number_input("금액 (원)", min_value=0, step=10000, key="rc_amt")
            rc_day = st.number_input("매월 결제일", min_value=1, max_value=31, value=1, key="rc_day")
            rc_desc = st.text_input("내용", placeholder="월세, 넷플릭스 등", key="rc_desc")

            if st.form_submit_button("등록") and rc_amount > 0 and rc_category:
                entry = BudgetEntry(
                    date=_date.today().isoformat(),
                    amount=rc_amount,
                    type="expense" if rc_type == "지출" else "income",
                    category=rc_category,
                    description=rc_desc,
                    is_recurring=1,
                    recurring_day=rc_day,
                )
                rem.add_recurring(entry)
                st.success("고정지출 등록 완료!")
                st.rerun()

        if st.button("이번 달 고정지출 자동 반영"):
            applied = rem.auto_apply_recurring(current_ym)
            if applied > 0:
                st.success(f"{applied}건 자동 반영 완료!")
            else:
                st.info("이미 모두 반영되었거나 고정지출이 없습니다.")

    # --- 가계부 Sub-tab 5: AI 분석 ---
    with btab5:
        from budget.analyzer import BudgetAnalyzer
        ba5 = BudgetAnalyzer()

        st.subheader("AI 소비 패턴 분석")

        if st.button("소비 패턴 분석 실행 (llama3.1:8b)"):
            try:
                from agent.budget_analyst import BudgetAIAnalyst
                ai = BudgetAIAnalyst()
                summary5 = ba5.get_monthly_summary(current_ym)
                cat_data = ba5.get_category_breakdown(current_ym)
                trend5 = ba5.get_monthly_trend(3)

                summary_dict = {
                    "total_income": summary5.total_income,
                    "total_expense": summary5.total_expense,
                    "savings": summary5.savings,
                    "savings_rate": summary5.savings_rate,
                }
                cat_list = cat_data.to_dict("records") if not cat_data.empty else []
                trend_list = trend5.to_dict("records") if not trend5.empty else []

                with st.spinner("AI 분석 중..."):
                    analysis = ai.analyze_spending_patterns(summary_dict, cat_list, trend_list)
                st.markdown(analysis)
            except Exception as e:
                st.error(f"AI 분석 실패: {e}")

        st.divider()
        st.subheader("월별 종합 리포트")

        if st.button("월별 리포트 생성 (qwen3.5:27b)"):
            try:
                from agent.budget_analyst import BudgetAIAnalyst
                ai = BudgetAIAnalyst()
                summary5 = ba5.get_monthly_summary(current_ym)
                cat_data = ba5.get_category_breakdown(current_ym)
                trend5 = ba5.get_monthly_trend(6)
                investable5 = ba5.calculate_investable_amount(current_ym)

                summary_dict = {
                    "total_income": summary5.total_income,
                    "total_expense": summary5.total_expense,
                    "savings": summary5.savings,
                    "savings_rate": summary5.savings_rate,
                }

                with st.spinner("AI 리포트 생성 중..."):
                    report = ai.generate_monthly_report(
                        summary_dict,
                        cat_data.to_dict("records") if not cat_data.empty else [],
                        trend5.to_dict("records") if not trend5.empty else [],
                        investable5,
                    )
                st.markdown(report)
            except Exception as e:
                st.error(f"리포트 생성 실패: {e}")

    # --- 가계부 Sub-tab 6: 투자 연계 ---
    with btab6:
        from budget.analyzer import BudgetAnalyzer
        ba6 = BudgetAnalyzer()

        st.subheader("투자 가능 여유자금 분석")

        investable_data = ba6.calculate_investable_amount(current_ym)

        col1, col2, col3 = st.columns(3)
        col1.metric("월 저축", f"{investable_data['monthly_savings']:,.0f}원")
        col2.metric("비상금 월적립 필요", f"{investable_data['emergency_reserve_needed'] / 12:,.0f}원")
        col3.metric("투자 가능 여유자금", f"{investable_data['investable_amount']:,.0f}원")

        st.caption(f"기준: 월 수입 {investable_data['monthly_income']:,.0f}원 - 월 지출 {investable_data['monthly_expense']:,.0f}원, 비상금 3개월분 월적립 차감")

        # 투자 예산 반영 버튼
        inv_amount = investable_data["investable_amount"]
        if inv_amount > 0:
            if st.button("이 금액을 사이드바 투자 예산에 반영", key="apply_invest_budget"):
                st.session_state["invest_budget"] = int(inv_amount)
                st.success(f"투자 예산이 {inv_amount:,.0f}원으로 반영되었습니다. 페이지를 새로고침하면 사이드바에 적용됩니다.")
                st.rerun()

        # 투자 적정성 지표
        if investable_data["monthly_income"] > 0:
            try:
                _, port_df_check = load_portfolio_data()
                pv = port_df_check["평가금액(원)"].sum() if not port_df_check.empty else 0
                monthly_inc = investable_data["monthly_income"]
                if pv > 0 and monthly_inc > 0:
                    invest_to_income = pv / (monthly_inc * 12)
                    st.info(f"투자자산/연소득 비율: {invest_to_income:.1f}배 — {'적정 수준' if invest_to_income < 3 else '높은 투자 비중 (리스크 관리 필요)'}")
            except Exception:
                pass

        # 총 자산 현황
        st.divider()
        st.subheader("총 자산 현황")
        try:
            _, port_df = load_portfolio_data()
            portfolio_value = port_df["평가금액(원)"].sum() if not port_df.empty else 0

            trend6 = ba6.get_monthly_trend(12)
            total_savings = trend6["savings"].sum() if not trend6.empty else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("투자자산", f"{portfolio_value:,.0f}원")
            col2.metric("누적 저축", f"{total_savings:,.0f}원")
            col3.metric("추정 총 자산", f"{portfolio_value + max(0, total_savings):,.0f}원")

            if portfolio_value > 0 or total_savings > 0:
                asset_data = pd.DataFrame({
                    "구분": ["투자자산", "저축"],
                    "금액": [portfolio_value, max(0, total_savings)],
                })
                fig_asset = px.pie(asset_data, names="구분", values="금액", title="자산 구성")
                st.plotly_chart(fig_asset, use_container_width=True)
        except Exception:
            st.info("포트폴리오 데이터를 불러올 수 없습니다.")

        # AI 투자 예산 추천
        st.divider()
        if st.button("AI 투자 예산 추천"):
            try:
                from agent.budget_analyst import BudgetAIAnalyst
                ai = BudgetAIAnalyst()
                portfolio_summary = pm.get_portfolio_summary()
                with st.spinner("AI 분석 중..."):
                    suggestion = ai.suggest_investment_budget(investable_data, portfolio_summary)
                st.markdown(suggestion)
            except Exception as e:
                st.error(f"추천 실패: {e}")


# === Tab 9: 종목 스크리너 ===
with tab9:
    st.subheader("종목 스크리너")
    st.caption("PER, PBR, 배당수익률 등으로 한국/미국 시장을 스크리닝합니다.")

    scr_market = st.selectbox("시장 선택", ["KOSPI", "KOSDAQ", "S&P 500 주요종목"], key="scr_market")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        scr_per_max = st.number_input("PER 최대", value=20.0, min_value=1.0, max_value=200.0, key="scr_per")
    with col2:
        scr_pbr_max = st.number_input("PBR 최대", value=3.0, min_value=0.1, max_value=50.0, key="scr_pbr")
    with col3:
        scr_div_min = st.number_input("배당수익률 최소 (%)", value=0.0, min_value=0.0, max_value=20.0, key="scr_div")
    with col4:
        scr_roe_min = st.number_input("ROE 최소 (%)", value=0.0, min_value=0.0, max_value=100.0, key="scr_roe")

    if st.button("스크리닝 실행", type="primary", key="run_screener"):
        from analysis.screener import screen_kr_market, screen_us_stocks

        filters = {
            "per_max": scr_per_max,
            "pbr_max": scr_pbr_max,
            "div_min": scr_div_min,
            "roe_min": scr_roe_min,
        }

        with st.spinner("스크리닝 중..."):
            if scr_market in ["KOSPI", "KOSDAQ"]:
                scr_df = screen_kr_market(scr_market, filters)
            else:
                scr_df = screen_us_stocks(filters=filters)

        if scr_df.empty:
            st.info("조건에 맞는 종목이 없습니다.")
        else:
            st.success(f"{len(scr_df)}개 종목이 조건에 부합합니다.")
            st.dataframe(scr_df, use_container_width=True, hide_index=True)
            st.session_state["screener_results"] = scr_df


# === Tab 10: 목표 시뮬레이션 ===
with tab10:
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
        from analysis.monte_carlo import simulate
        import numpy as np

        with st.spinner("1,000회 시뮬레이션 실행 중..."):
            mc_result = simulate(
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


# === Tab 11: 관심종목 ===
with tab11:
    from portfolio.watchlist import WatchlistManager
    wm = WatchlistManager()

    st.subheader("관심종목 관리")

    # 추가 폼
    with st.expander("관심종목 추가"):
        wcol1, wcol2, wcol3 = st.columns(3)
        with wcol1:
            w_ticker = st.text_input("티커", placeholder="005930 또는 AAPL", key="w_ticker")
        with wcol2:
            w_market = st.selectbox("시장", ["KR", "US", "ETF"], key="w_market")
        with wcol3:
            w_name = st.text_input("종목명", placeholder="삼성전자", key="w_name")

        wcol4, wcol5 = st.columns(2)
        with wcol4:
            w_low = st.number_input("목표 매수가", value=0.0, step=1000.0, format="%.0f", key="w_low")
        with wcol5:
            w_high = st.number_input("목표 매도가", value=0.0, step=1000.0, format="%.0f", key="w_high")

        w_note = st.text_input("메모", key="w_note")

        if st.button("관심종목 추가", key="add_watchlist"):
            if w_ticker and w_name:
                wm.add(
                    w_ticker, w_market, w_name,
                    target_price_low=w_low if w_low > 0 else None,
                    target_price_high=w_high if w_high > 0 else None,
                    note=w_note,
                )
                st.success(f"{w_name} 추가 완료!")
                st.rerun()
            else:
                st.warning("티커와 종목명을 입력하세요.")

    # 관심종목 현황
    watchlist = wm.get_all()
    if not watchlist:
        st.info("관심종목을 추가하세요.")
    else:
        if st.button("가격 업데이트", key="refresh_watchlist"):
            with st.spinner("관심종목 가격 조회 중..."):
                alerts = wm.check_alerts()
                st.session_state["watchlist_alerts"] = alerts

        if "watchlist_alerts" in st.session_state:
            alerts = st.session_state["watchlist_alerts"]

            # 알림 표시
            for a in alerts:
                if a.get("alert_type"):
                    st.warning(f"🔔 {a['name']} ({a['ticker']}): {a['alert_type']} — 현재가 {a['current_price']:,.0f}")

            # 테이블
            watch_rows = []
            for a in alerts:
                row = {
                    "종목": f"{a['name']} ({a['ticker']})",
                    "현재가": f"{a['current_price']:,.0f}",
                    "변동률": f"{a['change_pct']:+.2f}%",
                }
                if a["target_low"]:
                    row["매수 목표"] = f"{a['target_low']:,.0f}"
                    row["목표까지"] = f"{a['distance_to_low']:+.1f}%" if a["distance_to_low"] is not None else "-"
                else:
                    row["매수 목표"] = "-"
                    row["목표까지"] = "-"
                if a["target_high"]:
                    row["매도 목표"] = f"{a['target_high']:,.0f}"
                else:
                    row["매도 목표"] = "-"
                watch_rows.append(row)

            if watch_rows:
                st.dataframe(pd.DataFrame(watch_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("'가격 업데이트' 버튼을 눌러 현재가를 확인하세요.")

        # 삭제
        st.divider()
        del_items = [(w["id"], f"{w['name']} ({w['ticker']})") for w in watchlist]
        del_choice = st.selectbox("삭제할 종목", options=del_items, format_func=lambda x: x[1], key="del_watchlist")
        if st.button("관심종목 삭제", key="remove_watchlist"):
            wm.remove(del_choice[0])
            st.success("삭제 완료!")
            if "watchlist_alerts" in st.session_state:
                del st.session_state["watchlist_alerts"]
            st.rerun()
