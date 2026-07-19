import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from analysis.technical import TechnicalAnalyzer


def render(ctx):
    pm = ctx.pm
    fetcher = ctx.fetcher
    market_proc = ctx.market_proc
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

                    # OHLCV 컬럼 추출 (yfinance 영문 / pykrx 한글 모두 지원)
                    def _col(df, *names):
                        for nm in names:
                            if nm in df.columns:
                                return df[nm]
                        return None

                    high = _col(price_df, "High", "고가")
                    low = _col(price_df, "Low", "저가")
                    volume = _col(price_df, "Volume", "거래량")

                    # 기술적 지표 계산 (스토캐스틱/OBV는 OHLCV 제공 시 반영)
                    ta = TechnicalAnalyzer()
                    signal = ta.get_signal_summary(prices, high=high, low=low, volume=volume)

                    # 신호 요약
                    st.subheader(f"{label} 기술적 분석")
                    signal_colors = {"매수 우위": "green", "매도 우위": "red", "중립": "orange"}
                    st.markdown(
                        f"**종합 신호**: :{signal_colors.get(signal['signal'], 'gray')}[{signal['signal']}]"
                    )

                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    col1.metric("RSI(14)", f"{signal.get('rsi', 'N/A')}")
                    col2.metric("MACD", f"{signal.get('macd', 'N/A')}")
                    col3.metric("BB 위치", signal.get("bb_position", "N/A"))
                    col4.metric("MA20 대비", signal.get("price_vs_ma20", "N/A"))
                    stoch_k = signal.get("stochastic_k")
                    col5.metric("스토캐스틱 %K", f"{stoch_k}" if stoch_k is not None else "N/A")
                    col6.metric("OBV 추세", signal.get("obv_trend") or "N/A")

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

                    # 추가 지표: 일목균형표 / 스토캐스틱 / OBV
                    if high is not None and low is not None:
                        st.markdown("#### 추가 지표: 일목균형표 · 스토캐스틱 · OBV")
                        ichi = ta.ichimoku(high, low, prices)
                        stoch = ta.stochastic(high, low, prices)

                        n_rows = 3 if volume is not None else 2
                        titles = ["가격 & 일목균형표(구름대)", "스토캐스틱 %K/%D"]
                        heights = [0.5, 0.25]
                        if volume is not None:
                            titles.append("OBV")
                            heights.append(0.25)

                        fig2 = make_subplots(
                            rows=n_rows, cols=1, shared_xaxes=True,
                            vertical_spacing=0.06, row_heights=heights,
                            subplot_titles=titles,
                        )
                        # 가격 + 선행스팬 구름대
                        fig2.add_trace(go.Scatter(x=prices.index, y=prices, name="종가", line=dict(color="black")), row=1, col=1)
                        fig2.add_trace(go.Scatter(x=prices.index, y=ichi["tenkan"], name="전환선", line=dict(color="blue", width=1)), row=1, col=1)
                        fig2.add_trace(go.Scatter(x=prices.index, y=ichi["kijun"], name="기준선", line=dict(color="red", width=1)), row=1, col=1)
                        fig2.add_trace(go.Scatter(x=prices.index, y=ichi["senkou_a"], name="선행스팬A", line=dict(color="green", width=0.5)), row=1, col=1)
                        fig2.add_trace(go.Scatter(x=prices.index, y=ichi["senkou_b"], name="선행스팬B", line=dict(color="orange", width=0.5), fill="tonexty", fillcolor="rgba(0,200,0,0.08)"), row=1, col=1)
                        # 스토캐스틱
                        fig2.add_trace(go.Scatter(x=stoch["k"].index, y=stoch["k"], name="%K", line=dict(color="purple")), row=2, col=1)
                        fig2.add_trace(go.Scatter(x=stoch["d"].index, y=stoch["d"], name="%D", line=dict(color="gray", dash="dash")), row=2, col=1)
                        fig2.add_hline(y=80, line_dash="dash", line_color="red", row=2, col=1)
                        fig2.add_hline(y=20, line_dash="dash", line_color="green", row=2, col=1)
                        # OBV
                        if volume is not None:
                            obv_series = ta.obv(prices, volume)
                            fig2.add_trace(go.Scatter(x=obv_series.index, y=obv_series, name="OBV", line=dict(color="teal")), row=3, col=1)

                        fig2.update_layout(height=800, showlegend=True, hovermode="x unified")
                        st.plotly_chart(fig2, use_container_width=True, key="tech_extra_indicators")

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
