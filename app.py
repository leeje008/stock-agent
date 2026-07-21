import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd

from db.database import init_db
from db.models import Holding
from portfolio.manager import PortfolioManager
from portfolio.tracker import PortfolioTracker
from data.fetcher import StockDataFetcher
from data.market_data import MarketDataProcessor
from data.news_fetcher import NewsFetcher
from utils.constants import RISK_LEVELS, DISCLAIMER, KR_STOCK_MAP
from utils.fx import get_usd_krw_rate
from portfolio.isa_manager import IsaManager, get_or_create_default_account
from db.models import IsaAccount, MonthlyContribution
from ui.context import AppContext
from ui.tabs import (
    tab_1, tab_2, tab_3, tab_4, tab_5, tab_6, tab_7, tab_8, tab_9, tab_10, tab_11,
    tab_risk, tab_tax,
)

# --- 초기 설정 ---
st.set_page_config(page_title="주식 포트폴리오 에이전트", layout="wide")
init_db()

pm = PortfolioManager()
fetcher = StockDataFetcher()
market_proc = MarketDataProcessor()
news_fetcher = NewsFetcher()
tracker = PortfolioTracker()
isa_mgr = IsaManager()
isa_account = get_or_create_default_account()


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
                    if added:
                        msg.append(f"{added}개 신규 추가")
                    if updated:
                        msg.append(f"{updated}개 기존 종목 업데이트")
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

    # === ISA 계좌 (적립식) ===
    st.subheader("ISA 계좌")
    with st.expander("ISA 계좌 설정", expanded=False):
        new_monthly = st.number_input(
            "월 적립금 (원)",
            value=int(isa_account.monthly_contribution),
            step=100_000, format="%d", key="isa_monthly_input",
        )
        new_risk = st.selectbox(
            "위험성향 (DCA 비중 결정)",
            options=list(RISK_LEVELS.keys()),
            index=list(RISK_LEVELS.keys()).index(isa_account.risk_level)
                  if isa_account.risk_level in RISK_LEVELS else 2,
            key="isa_risk_input",
        )
        new_start = st.text_input(
            "시작일 (YYYY-MM-DD)",
            value=isa_account.start_date or "",
            key="isa_start_input",
        )
        if st.button("ISA 설정 저장", key="isa_save_btn"):
            isa_mgr.upsert_account(IsaAccount(
                account_name=isa_account.account_name,
                monthly_contribution=float(new_monthly),
                risk_level=new_risk,
                start_date=new_start or None,
                annual_limit=isa_account.annual_limit,
                tax_status=isa_account.tax_status,
                note=isa_account.note,
            ))
            st.success("ISA 설정 저장 완료")
            st.rerun()

    # 누적 납입액 / 잔여 한도
    from datetime import datetime as _dt
    _year = _dt.today().year
    _yymm = _dt.today().strftime("%Y-%m")
    _year_total = isa_mgr.get_year_total(isa_account.id, _year)
    _remaining = max(0.0, isa_account.annual_limit - _year_total)
    col_a, col_b = st.columns(2)
    col_a.metric(f"{_year}년 납입액", f"{_year_total:,.0f}원")
    col_b.metric("잔여 한도", f"{_remaining:,.0f}원")

    # 이번 달 매수 빠른 입력
    with st.form("isa_quick_buy_form"):
        st.caption("이번 달 매수 기록 (단순 폼)")
        c1, c2 = st.columns(2)
        with c1:
            qb_date = st.date_input("거래일", value=_dt.today(), key="isa_qb_date")
            qb_qty = st.number_input("수량", min_value=0, value=0, key="isa_qb_qty")
        with c2:
            qb_ticker = st.text_input("티커", placeholder="360750 / VOO", key="isa_qb_ticker")
            qb_price = st.number_input("가격", min_value=0.0, value=0.0, format="%.2f", key="isa_qb_price")
        qb_name = st.text_input("종목명 (선택)", placeholder="TIGER 미국S&P500", key="isa_qb_name")
        qb_submitted = st.form_submit_button("이번 달 매수 추가")

    if qb_submitted and qb_ticker and qb_qty > 0 and qb_price > 0:
        from broker.aggregator import TransactionAggregator
        ticker = qb_ticker.strip().upper()
        if ticker.startswith("A") and ticker[1:].isdigit():
            ticker = ticker[1:]
        is_kr = ticker.isdigit() and len(ticker) == 6
        if is_kr and len(ticker) < 6:
            ticker = ticker.zfill(6)
        market = "KR" if is_kr else "US"
        currency = "KRW" if is_kr else "USD"
        amount = qb_qty * qb_price

        # 거래내역 + 보유종목 갱신
        tx = {
            "date": qb_date.strftime("%Y-%m-%d"),
            "ticker": ticker,
            "name": qb_name or ticker,
            "action": "BUY",
            "quantity": int(qb_qty),
            "price": float(qb_price),
            "amount": float(amount),
            "fee": 0.0, "tax": 0.0,
            "currency": currency, "market": market,
        }
        pm.record_transactions_batch([tx])
        existing = pm.get_holding_by_ticker(ticker)
        if existing:
            new_qty = existing.quantity + int(qb_qty)
            new_avg = (existing.quantity * existing.avg_price + amount) / new_qty
            pm.update_or_merge_holding(existing.id, new_qty, new_avg)
        else:
            pm.add_holding(Holding(
                ticker=ticker, market=market, name=qb_name or ticker,
                quantity=int(qb_qty), avg_price=float(qb_price), currency=currency,
            ))

        # 월별 납입 누적 (KRW 기준; USD면 환율 곱)
        krw_amount = amount if currency == "KRW" else amount * get_usd_krw_rate()
        existing_contrib = next(
            (c for c in isa_mgr.get_contributions(isa_account.id) if c.year_month == _yymm),
            None,
        )
        new_total = (existing_contrib.amount if existing_contrib else 0) + krw_amount
        isa_mgr.record_contribution(MonthlyContribution(
            account_id=isa_account.id, year_month=_yymm,
            amount=new_total, note="quick_buy",
        ))
        st.success(f"{ticker} {qb_qty}주 기록 ({krw_amount:,.0f}원)")
        st.rerun()

    # ISA 전용 CSV 업로드 (단순 양식)
    with st.expander("ISA CSV 업로드 (단순 양식)"):
        st.caption("컬럼: date, ticker, name, quantity, price, [contribution_amount], [market]")
        isa_csv = st.file_uploader(
            "ISA 매수 CSV", type=["csv", "xlsx", "xls"], key="isa_csv_upload"
        )
        if isa_csv is not None:
            try:
                from broker.manual_isa import parse as isa_parse
                rows = isa_parse(isa_csv.read(), isa_csv.name)
                if not rows:
                    st.warning("파싱된 거래 내역이 없습니다.")
                else:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    if st.button("ISA 거래 일괄 반영", key="isa_csv_apply"):
                        inserted, skipped = pm.record_transactions_batch(rows)
                        # 월별 납입 누적
                        by_month: dict[str, float] = {}
                        for r in rows:
                            ym = r["date"][:7]
                            krw = r["contribution_amount"] if r["currency"] == "KRW" \
                                  else r["contribution_amount"] * get_usd_krw_rate()
                            by_month[ym] = by_month.get(ym, 0.0) + krw
                        for ym, total in by_month.items():
                            existing_c = next(
                                (c for c in isa_mgr.get_contributions(isa_account.id)
                                 if c.year_month == ym),
                                None,
                            )
                            merged = (existing_c.amount if existing_c else 0) + total
                            isa_mgr.record_contribution(MonthlyContribution(
                                account_id=isa_account.id, year_month=ym,
                                amount=merged, note="csv_upload",
                            ))
                        st.success(f"{inserted}건 거래 반영 (중복 {skipped}건 제외)")
                        st.rerun()
            except Exception as e:
                st.error(f"파일 처리 실패: {e}")

        # ISA 템플릿 다운로드
        try:
            from broker.manual_isa import template as isa_template
            tdf = isa_template()
            st.download_button(
                "ISA 템플릿 다운로드 (CSV)",
                data=tdf.to_csv(index=False, encoding="utf-8-sig"),
                file_name="isa_매수_템플릿.csv",
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

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13 = st.tabs(
    ["포트폴리오 현황", "최적화 결과", "뉴스 & 시장 분석", "매수 가이드", "기술적 분석", "백테스팅", "AI 토론", "가계부", "종목 스크리너", "목표 시뮬레이션", "관심종목", "리스크 관리", "세금 계산기"]
)




# === App Context 구성 ===
ctx = AppContext(
    pm=pm,
    fetcher=fetcher,
    market_proc=market_proc,
    news_fetcher=news_fetcher,
    tracker=tracker,
    isa_mgr=isa_mgr,
    isa_account=isa_account,
    budget=budget,
    risk_level=risk_level,
    strategy=strategy,
)


with tab1:
    tab_1.render(ctx)

with tab2:
    tab_2.render(ctx)

with tab3:
    tab_3.render(ctx)

with tab4:
    tab_4.render(ctx)

with tab5:
    tab_5.render(ctx)

with tab6:
    tab_6.render(ctx)

with tab7:
    tab_7.render(ctx)

with tab8:
    tab_8.render(ctx)

with tab9:
    tab_9.render(ctx)

with tab10:
    tab_10.render(ctx)

with tab11:
    tab_11.render(ctx)

with tab12:
    tab_risk.render(ctx)

with tab13:
    tab_tax.render(ctx)
