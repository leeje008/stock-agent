import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render(ctx):
    pm = ctx.pm
    load_portfolio_data = ctx.load_portfolio_data
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
