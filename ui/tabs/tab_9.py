import streamlit as st


def render(ctx):
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
        from ui.data_cache import screen_market_cached

        filters_items = (
            ("per_max", scr_per_max),
            ("pbr_max", scr_pbr_max),
            ("div_min", scr_div_min),
            ("roe_min", scr_roe_min),
        )

        with st.spinner("스크리닝 중..."):
            scr_df = screen_market_cached(scr_market, filters_items)

        if scr_df.empty:
            st.info("조건에 맞는 종목이 없습니다.")
        else:
            st.success(f"{len(scr_df)}개 종목이 조건에 부합합니다.")
            st.dataframe(scr_df, use_container_width=True, hide_index=True)
            st.session_state["screener_results"] = scr_df
