import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from portfolio.allocator import BudgetAllocator


def render(ctx):
    pm = ctx.pm
    fetcher = ctx.fetcher
    budget = ctx.budget
    strategy = ctx.strategy
    holdings = pm.get_all_holdings()

    if len(holdings) < 2:
        st.info("최적화를 실행하려면 최소 2개 이상의 종목이 필요합니다.")
    else:
        # 섹터 비중 상한 제약 (max_sharpe / min_volatility 전략에 적용)
        sectors = sorted({(h.sector or "기타") for h in holdings})
        use_sector_cap = st.checkbox(
            "섹터 비중 상한 제약 적용", value=False, key="use_sector_cap",
            help="선택한 상한을 넘지 않도록 섹터별 비중을 제한합니다 (최대 샤프/최소 변동성 전략).",
        )
        sector_cap_pct = 40
        if use_sector_cap:
            sector_cap_pct = st.slider(
                "섹터별 최대 비중 (%)", min_value=10, max_value=100, value=40, step=5,
                key="sector_cap_pct",
            )
            st.caption(f"감지된 섹터: {', '.join(sectors)}")

        # 종목별 최소/최대 비중 제약 (max_sharpe / min_volatility 전략에 적용)
        use_weight_bounds = st.checkbox(
            "종목 비중 상·하한 제약 적용", value=False, key="use_weight_bounds",
            help="각 종목의 비중이 지정한 최소~최대 범위를 벗어나지 않도록 제한합니다.",
        )
        wb_min, wb_max = 0, 100
        if use_weight_bounds:
            wb_min, wb_max = st.slider(
                "종목별 비중 범위 (%)", min_value=0, max_value=100, value=(0, 40), step=5,
                key="weight_bounds_range",
            )

        if st.button("최적화 실행", type="primary"):
            tickers = [{"ticker": h.ticker, "market": h.market} for h in holdings]
            allocator = BudgetAllocator()

            # 섹터 제약 구성
            sector_map = None
            sector_upper = None
            if use_sector_cap:
                sector_map = {h.ticker: (h.sector or "기타") for h in holdings}
                sector_upper = {s: sector_cap_pct / 100.0 for s in sectors}

            # 종목 비중 상·하한 구성
            weight_bounds = None
            if use_weight_bounds:
                weight_bounds = (wb_min / 100.0, wb_max / 100.0)

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
                    try:
                        result = allocator.generate_buy_guide(
                            tickers, budget, strategy=strat,
                            sector_map=sector_map, sector_upper=sector_upper,
                            weight_bounds=weight_bounds,
                        )
                    except Exception as e:
                        result = {
                            "error": (
                                "제약 조건으로는 최적 포트폴리오를 찾을 수 없습니다. "
                                "섹터 상한이나 종목 비중 범위를 완화해 주세요. "
                                f"(상세: {e})"
                            )
                        }
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        if use_sector_cap and strat in ("max_sharpe", "min_volatility"):
                            result["sector_cap"] = sector_cap_pct / 100.0
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
