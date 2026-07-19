import streamlit as st
import pandas as pd


def render(ctx):
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
