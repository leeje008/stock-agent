import pandas as pd
import streamlit as st

from analysis import tax as tax_calc
from utils.fx import get_usd_krw_rate


def render(ctx):
    pm = ctx.pm
    isa_mgr = ctx.isa_mgr
    isa_account = ctx.isa_account

    st.subheader("세금 계산기")
    st.caption(
        "⚠️ 아래 금액은 공개된 세율을 적용한 **참고용 추정치**이며 세무 자문이 아닙니다. "
        "실제 신고 세액은 보유기간·계좌유형·타 소득 등에 따라 달라질 수 있습니다."
    )

    # === 실현손익 (거래내역 기반) ===
    st.markdown("### 실현손익 (거래내역 기반)")
    # 실현손익은 전체 이력이 거래일 순으로 필요하다 (이동평균 원가)
    transactions = pm.get_all_transactions()
    try:
        fx_rate = get_usd_krw_rate()
    except Exception:
        fx_rate = 1350.0
    realized = tax_calc.realized_pnl_from_transactions(transactions, fx_rate=fx_rate)

    if not realized:
        st.info("매도(SELL) 거래내역이 없어 실현손익이 없습니다. 사이드바에서 거래내역을 업로드하세요.")
        total_gain = 0.0
    else:
        rows = [
            {
                "매도일": r["date"],
                "종목": r["name"],
                "티커": r["ticker"],
                "수량": f"{r['quantity']:,.0f}",
                "통화": r["currency"],
                "매도대금": f"{r['proceeds']:,.2f}",
                "취득원가": f"{r['cost_basis']:,.2f}",
                "실현손익": f"{r['gain']:,.2f}",
                "실현손익(원)": f"{r['gain_krw']:,.0f}",
            }
            for r in realized
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        total_gain = tax_calc.total_realized_gain(realized)
        st.caption(
            "이동평균 원가 방식이며 수수료·거래세를 차감했습니다. "
            f"외화 거래는 USD/KRW {fx_rate:,.0f} 을 적용해 원화로 환산했습니다."
        )

    # === 양도소득세 ===
    st.markdown("### 해외주식 양도소득세")
    # 키가 있는 위젯은 이후 재실행에서 value 인자를 무시하므로,
    # 거래내역에서 계산된 값이 바뀌면 session_state 를 직접 갱신한다.
    if st.session_state.get("_tax_gain_source") != total_gain:
        st.session_state["_tax_gain_source"] = total_gain
        st.session_state["tax_gain_input"] = int(total_gain)
    gain_input = st.number_input(
        "연간 실현 양도차익 (원)",
        step=100_000, format="%d", key="tax_gain_input",
        help="거래내역에서 자동 계산된 값이며 직접 수정할 수 있습니다.",
    )
    cg = tax_calc.capital_gains_tax(float(gain_input))
    c1, c2, c3 = st.columns(3)
    c1.metric("기본공제", f"{cg['deduction_used']:,.0f}원", help="연 250만원 기본공제")
    c2.metric("과세표준", f"{cg['taxable']:,.0f}원")
    c3.metric("예상 세액 (22%)", f"{cg['tax']:,.0f}원")
    if cg["taxable"] <= 0:
        st.success("기본공제(250만원) 이내로 예상 양도소득세가 없습니다.")

    # === 배당소득세 ===
    st.markdown("### 배당소득세")
    div_input = st.number_input(
        "연간 배당소득 (원)", value=0, step=100_000, format="%d", key="tax_dividend_input",
    )
    dv = tax_calc.dividend_tax(float(div_input))
    d1, d2 = st.columns(2)
    d1.metric("예상 세액 (15.4%)", f"{dv['tax']:,.0f}원")
    d2.metric("세후 배당", f"{dv['dividend_income'] - dv['tax']:,.0f}원")
    if dv["comprehensive_taxation"]:
        st.warning(
            f"금융소득이 {dv['threshold']:,.0f}원을 초과하여 **금융소득종합과세** 대상일 수 있습니다. "
            "이자·배당 합산 기준이므로 세무 전문가 상담을 권장합니다."
        )
    else:
        st.caption(f"금융소득종합과세 기준: 연 {dv['threshold']:,.0f}원 초과 시 대상")

    # === ISA 비과세 한도 ===
    st.markdown("### ISA 계좌 비과세 혜택")
    acc_type = isa_account.tax_status if isa_account else "general"
    type_label = {"general": "일반형", "flexible": "중개형", "reborn": "서민형"}.get(acc_type, acc_type)
    isa_profit = st.number_input(
        "ISA 계좌 순이익 (원)", value=0, step=100_000, format="%d", key="tax_isa_profit",
        help="ISA 계좌 내 이자·배당·매매차익 순이익 합계",
    )
    isa = tax_calc.isa_tax_benefit(float(isa_profit), acc_type)
    i1, i2, i3 = st.columns(3)
    i1.metric(f"비과세 한도 ({type_label})", f"{isa['exempt_limit']:,.0f}원")
    i2.metric("비과세 적용액", f"{isa['exempt_amount']:,.0f}원")
    i3.metric("예상 세액 (9.9%)", f"{isa['tax']:,.0f}원")
    if isa["saved_vs_normal"] > 0:
        st.success(f"일반 계좌(15.4%) 대비 약 {isa['saved_vs_normal']:,.0f}원 절세 효과가 예상됩니다.")

    # 연간 납입 한도 현황
    if isa_account and isa_account.id:
        from datetime import datetime as _dt
        year = _dt.today().year
        try:
            year_total = isa_mgr.get_year_total(isa_account.id, year)
            remaining = max(0.0, isa_account.annual_limit - year_total)
            r1, r2 = st.columns(2)
            r1.metric(f"{year}년 납입액", f"{year_total:,.0f}원")
            r2.metric("잔여 납입 한도", f"{remaining:,.0f}원")
        except Exception as e:
            st.caption(f"ISA 납입 현황 조회 실패: {e}")

    # === 참고: 환율 ===
    with st.expander("계산 기준 및 참고사항"):
        try:
            st.caption(f"USD/KRW 환율: {get_usd_krw_rate():,.0f} (해외 거래 원화 환산 시 적용)")
        except Exception:
            pass
        st.markdown(
            "- 해외주식 양도소득세: 연간 양도차익에서 기본공제 250만원 차감 후 22%(지방소득세 포함)\n"
            "- 배당소득세: 15.4% 원천징수. 금융소득 연 2,000만원 초과 시 종합과세 대상\n"
            "- ISA: 일반형 200만원 / 서민형 400만원까지 비과세, 초과분 9.9% 분리과세\n"
            "- 실현손익은 이동평균 원가 방식이며, 실제 신고 기준(선입선출 등)과 다를 수 있습니다."
        )
