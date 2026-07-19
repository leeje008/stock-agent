"""애플리케이션 공유 컨텍스트.

app.py의 사이드바에서 구성한 런타임 서비스/설정을 각 탭 render(ctx) 함수로
전달하기 위한 컨테이너. 기존 module-level 전역과 동일한 객체를 담는다.
"""
from dataclasses import dataclass
from typing import Any

import pandas as pd

from utils.fx import get_usd_krw_rate


@dataclass
class AppContext:
    pm: Any
    fetcher: Any
    market_proc: Any
    news_fetcher: Any
    tracker: Any
    isa_mgr: Any
    isa_account: Any
    budget: float
    risk_level: str
    strategy: str

    def load_portfolio_data(self):
        """포트폴리오 데이터를 로드하고 현재가/환율을 적용한 DataFrame 반환"""
        holdings = self.pm.get_all_holdings()
        if not holdings:
            return holdings, pd.DataFrame()

        fx_rate = get_usd_krw_rate()
        rows = []
        for h in holdings:
            current_price = None
            try:
                price_df = self.fetcher.get_price_data(h.ticker, h.market, period="5d")
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
