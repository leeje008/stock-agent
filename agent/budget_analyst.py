import json
from agent.llm_client import LLMClient


class BudgetAIAnalyst:
    """AI 가계부 분석 에이전트"""

    def __init__(self):
        self.llm = LLMClient()

    def analyze_spending_patterns(self, summary: dict, category_breakdown: list[dict], previous_months: list[dict]) -> str:
        """소비 패턴 분석 (light 모델)"""
        prompt = f"""당신은 가계부 전문 분석가입니다.

아래 이번 달 지출 데이터를 분석하여 절약 포인트를 찾아주세요.

## 이번 달 요약
- 수입: {summary.get('total_income', 0):,.0f}원
- 지출: {summary.get('total_expense', 0):,.0f}원
- 저축: {summary.get('savings', 0):,.0f}원
- 저축률: {summary.get('savings_rate', 0):.1f}%

## 카테고리별 지출
{json.dumps(category_breakdown, ensure_ascii=False, indent=2)}

## 이전 월 추이
{json.dumps(previous_months, ensure_ascii=False, indent=2)}

다음을 분석해주세요:
1. 지출이 가장 많은 카테고리와 절약 가능성
2. 전월 대비 증가한 카테고리
3. 구체적인 절약 팁 2~3가지
4. 저축률 평가 (목표: 30% 이상)"""

        return self.llm.generate(
            prompt,
            system="당신은 친근한 가계부 코치입니다. 실용적인 절약 조언을 제공합니다.",
            max_tokens=1500,
            model_tier="light",
        )

    def generate_monthly_report(self, summary: dict, category_breakdown: list[dict], trend_data: list[dict], investable: dict) -> str:
        """월별 종합 리포트 (heavy 모델)"""
        prompt = f"""당신은 개인 재무 관리 전문가입니다.

아래 데이터를 종합하여 이번 달 재무 리포트를 작성하세요.

## 이번 달 요약
{json.dumps(summary, ensure_ascii=False, indent=2)}

## 카테고리별 지출
{json.dumps(category_breakdown, ensure_ascii=False, indent=2)}

## 최근 6개월 추이
{json.dumps(trend_data, ensure_ascii=False, indent=2)}

## 투자 가능 여유자금 분석
{json.dumps(investable, ensure_ascii=False, indent=2)}

다음 형식으로 리포트를 작성하세요:

1. **이번 달 재무 성적표**: 수입/지출/저축 요약 및 등급 (A~F)
2. **지출 분석**: 카테고리별 상세 분석, 전월 대비 변화
3. **저축 현황**: 저축률 추이, 목표 달성 여부
4. **절약 추천**: 구체적인 절약 방안 3가지
5. **투자 추천**: 여유자금 기반 투자 가능 금액 및 배분 제안
6. **다음 달 목표**: 지출 조정 목표, 저축 목표"""

        return self.llm.generate(
            prompt,
            system="당신은 경험 많은 개인 재무 관리 전문가입니다. 데이터 기반의 실용적인 조언을 제공합니다.",
            max_tokens=2500,
            model_tier="heavy",
        )

    def suggest_investment_budget(self, investable: dict, portfolio_summary: dict) -> str:
        """투자 예산 추천 (light 모델)"""
        prompt = f"""가계부 분석 결과를 바탕으로 투자 예산을 추천해주세요.

## 가계부 분석
- 월 수입: {investable.get('monthly_income', 0):,.0f}원
- 월 지출: {investable.get('monthly_expense', 0):,.0f}원
- 월 저축: {investable.get('monthly_savings', 0):,.0f}원
- 저축률: {investable.get('savings_rate', 0):.1f}%
- 비상금 필요액: {investable.get('emergency_reserve_needed', 0):,.0f}원
- 투자 가능 여유자금: {investable.get('investable_amount', 0):,.0f}원

## 현재 포트폴리오
{json.dumps(portfolio_summary, ensure_ascii=False, indent=2, default=str)}

다음을 포함하여 답변하세요:
1. 추천 월 투자금액
2. 투자 가능 근거
3. 주의사항"""

        return self.llm.generate(
            prompt,
            system="당신은 개인 재무 설계사입니다. 보수적이고 안정적인 투자 예산을 추천합니다.",
            max_tokens=1000,
            model_tier="light",
        )
