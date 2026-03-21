import json
from datetime import datetime

from db.database import get_connection


class ReportGenerator:
    """분석 리포트 생성 및 저장"""

    def save_report(self, report_type: str, content: str, metadata: dict | None = None):
        conn = get_connection()
        conn.execute(
            """INSERT INTO analysis_reports (report_type, content, metadata_json)
               VALUES (?, ?, ?)""",
            (report_type, content, json.dumps(metadata, ensure_ascii=False) if metadata else None),
        )
        conn.commit()
        conn.close()

    def get_latest_report(self, report_type: str) -> dict | None:
        conn = get_connection()
        row = conn.execute(
            """SELECT * FROM analysis_reports
               WHERE report_type=?
               ORDER BY created_at DESC LIMIT 1""",
            (report_type,),
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def get_report_history(self, report_type: str, limit: int = 10) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            """SELECT * FROM analysis_reports
               WHERE report_type=?
               ORDER BY created_at DESC LIMIT ?""",
            (report_type, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def format_portfolio_report(
        self,
        portfolio_summary: dict,
        optimization: dict,
        news_analysis: dict | None,
        recommendation: str,
    ) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        report = f"""# 포트폴리오 분석 리포트
**생성 시각**: {now}

---

## 1. 포트폴리오 현황
- 보유 종목 수: {portfolio_summary.get('total_holdings', 0)}개

| 종목 | 시장 | 수량 | 평균매입가 |
|------|------|------|-----------|
"""
        for h in portfolio_summary.get("holdings", []):
            report += f"| {h['name']} ({h['ticker']}) | {h['market']} | {h['quantity']} | {h['avg_price']:,.0f} |\n"

        if optimization:
            report += f"""
---

## 2. 최적화 결과
- 전략: {optimization.get('strategy', 'N/A')}
- 기대 수익률: {optimization.get('expected_return', 0):.2%}
- 변동성: {optimization.get('volatility', 0):.2%}
- 샤프 비율: {optimization.get('sharpe_ratio', 0):.2f}
"""

        report += f"""
---

## 3. AI 투자 추천

{recommendation}

---

*본 정보는 투자 권유가 아니며, 투자 결정의 책임은 사용자에게 있습니다.*
"""
        return report
