import streamlit as st
import pandas as pd
import plotly.express as px

from analysis import risk
from portfolio.rebalancer import Rebalancer
from ui.data_cache import get_multiple_prices_cached, get_price_data_cached, tickers_to_key


def render(ctx):
    pm = ctx.pm
    fetcher = ctx.fetcher
    load_portfolio_data = ctx.load_portfolio_data

    st.subheader("리스크 관리 대시보드")
    holdings = pm.get_all_holdings()
    if len(holdings) < 1:
        st.info("포트폴리오에 종목을 추가하세요.")
        return

    _, port_df = load_portfolio_data()
    if port_df.empty:
        st.warning("포트폴리오 데이터를 불러올 수 없습니다.")
        return

    name_map = {h.ticker: h.name for h in holdings}

    # 현재 비중
    weights = Rebalancer.compute_current_weights(port_df)
    if not weights:
        st.warning("평가금액 데이터가 부족합니다.")
        return

    # 시세(종가) 수집 → VaR/CVaR/상관 (매 재실행마다 도는 경로이므로 캐시 사용)
    with st.spinner("시세 데이터 수집 중..."):
        prices = get_multiple_prices_cached(tickers_to_key(holdings), "1y", _fetcher=fetcher)

    # === VaR / CVaR ===
    st.markdown("### 손실 위험 (Historical VaR / CVaR, 95%)")
    if prices.empty or len(prices.columns) < 1:
        st.caption("VaR/CVaR 계산을 위한 시세 데이터가 부족합니다.")
    else:
        var95 = risk.portfolio_var(prices, weights, alpha=0.95)
        cvar95 = risk.portfolio_cvar(prices, weights, alpha=0.95)
        hhi = risk.herfindahl_index(weights)
        total_value = float(port_df["평가금액(원)"].sum())

        c1, c2, c3 = st.columns(3)
        c1.metric("1일 VaR (95%)", f"{var95:.2%}", help="정상 시장에서 하루 최대 예상 손실률(신뢰 95%)")
        c2.metric("1일 CVaR (95%)", f"{cvar95:.2%}", help="VaR를 초과하는 꼬리 구간의 평균 손실률")
        c3.metric("집중도 (HHI)", f"{hhi:.3f}", help="0에 가까울수록 분산, 1에 가까울수록 집중")

        st.caption(
            f"평가금액 {total_value:,.0f}원 기준 예상 1일 최대손실(VaR): "
            f"약 {total_value * var95:,.0f}원 · 꼬리손실(CVaR): 약 {total_value * cvar95:,.0f}원"
        )

        # VaR 방법론 3종 병기
        pvar = risk.parametric_var(prices, weights, alpha=0.95)
        mvar = risk.monte_carlo_var(prices, weights, alpha=0.95)
        st.markdown("**VaR 방법론 비교 (1일, 95%)**")
        vcol1, vcol2, vcol3 = st.columns(3)
        vcol1.metric("히스토리컬", f"{var95:.2%}", help="실제 과거 수익률 분포의 5% 분위수")
        vcol2.metric("파라메트릭", f"{pvar:.2%}", help="정규분포 가정(평균·표준편차) 기반")
        vcol3.metric("몬테카를로", f"{mvar:.2%}", help="정규분포 파라미터로 1만회 시뮬레이션")

        # 시장충격 스트레스 시나리오
        st.markdown("### 시장충격 스트레스 시나리오")
        stress = risk.stress_scenarios(total_value, [-0.05, -0.10, -0.20, -0.30])
        stress_df = pd.DataFrame([
            {
                "시장충격": f"{s['shock']:.0%}",
                "예상 손실률": f"{s['loss_pct']:.0%}",
                "예상 손실금액(원)": f"{s['loss_amount']:,.0f}",
            }
            for s in stress
        ])
        st.dataframe(stress_df, use_container_width=True, hide_index=True)
        st.caption("포트폴리오가 시장과 동일하게 움직인다고 가정한 단순 충격 시나리오입니다.")

    # === 벤치마크 대비 베타 ===
    st.markdown("### 벤치마크 대비 베타")
    if prices.empty or len(prices.columns) < 1:
        st.caption("베타 계산을 위한 시세 데이터가 부족합니다.")
    else:
        bench_options = {"S&P500 (^GSPC)": "^GSPC", "NASDAQ100 (^NDX)": "^NDX", "KOSPI (^KS11)": "^KS11"}
        bench_label = st.selectbox("벤치마크 선택", list(bench_options), index=0, key="risk_benchmark")
        bench_ticker = bench_options[bench_label]
        try:
            bench_df = get_price_data_cached(bench_ticker, "US", "1y", _fetcher=fetcher)
            if bench_df.empty:
                st.caption("벤치마크 시세를 가져올 수 없습니다.")
            else:
                close_col = "Close" if "Close" in bench_df.columns else "종가"
                bench_returns = bench_df[close_col].pct_change().dropna()
                beta = risk.portfolio_beta(prices, weights, bench_returns)
                b1, b2 = st.columns(2)
                b1.metric(f"베타 (vs {bench_label})", f"{beta:.2f}",
                          help="1보다 크면 시장보다 변동성이 큼, 작으면 방어적")
                interp = "시장보다 공격적" if beta > 1.05 else ("시장보다 방어적" if beta < 0.95 else "시장과 유사")
                b2.metric("해석", interp)
        except Exception as e:
            st.caption(f"베타 계산 실패: {e}")

    # === 상관관계 히트맵 ===
    st.markdown("### 종목 간 상관관계")
    if prices.empty or len(prices.columns) < 2:
        st.caption("상관관계 분석에는 2개 이상의 종목 시세가 필요합니다.")
    else:
        corr = risk.correlation_matrix(prices)
        if not corr.empty:
            labels = [name_map.get(t, t) for t in corr.columns]
            fig = px.imshow(
                corr.values, x=labels, y=labels,
                color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
                text_auto=".2f", title="수익률 상관관계 매트릭스",
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True, key="risk_corr_heatmap")
            st.caption("해석: >0.7 높은 상관(분산효과 낮음) · <0.3 낮은 상관(분산효과 높음)")

    # === 집중도 경고 ===
    st.markdown("### 집중도 경고")
    alerts = risk.concentration_alerts(weights, threshold=0.30)
    if not alerts:
        st.success("단일 종목 비중이 30%를 초과하는 종목이 없습니다.")
    else:
        for a in alerts:
            label = name_map.get(a["ticker"], a["ticker"])
            icon = "🔴" if a["severity"] == "high" else "🟠"
            st.warning(f"{icon} {label} ({a['ticker']}) 비중 {a['weight']:.1%} — 30% 초과")

    # === 목표 대비 리밸런싱 이탈 알림 ===
    st.markdown("### 목표 대비 리밸런싱 알림")
    rb = Rebalancer()
    targets = rb.get_targets()
    if not targets:
        st.info("리밸런싱 목표 비중이 설정되지 않았습니다. '최적화 결과' 탭에서 목표를 설정하세요.")
    else:
        threshold_pct = st.slider(
            "이탈 임계치 (%p)", min_value=1, max_value=20, value=5, step=1, key="risk_drift_thr"
        )
        drift_alerts = rb.alerts_from_portfolio(port_df, threshold=threshold_pct / 100.0)
        if not drift_alerts:
            st.success(f"모든 종목이 목표 비중 대비 ±{threshold_pct}%p 이내입니다.")
        else:
            rows = []
            for d in drift_alerts:
                rows.append({
                    "종목": name_map.get(d["ticker"], d["ticker"]),
                    "티커": d["ticker"],
                    "현재비중": f"{d['current']:.1%}",
                    "목표비중": f"{d['target']:.1%}",
                    "이탈": f"{d['drift']:+.1%}",
                    "조치": d["action"],
                    "심각도": d["severity"],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption("이탈이 임계치를 초과한 종목입니다. 조치 열은 목표 복귀를 위한 매매 방향입니다.")
