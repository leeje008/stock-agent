import json

from agent.llm_client import LLMClient


class PortfolioManagerAgent:
    """모든 분석 결과를 종합하여 최종 투자 추천 리포트 생성"""

    def __init__(self):
        self.llm = LLMClient()

    def generate_recommendation(
        self,
        current_portfolio: dict,
        optimization_result: dict,
        news_analysis: dict,
        macro_data: dict,
        budget: float,
    ) -> str:
        prompt = f"""당신은 개인 투자자를 위한 포트폴리오 매니저입니다.

아래 정보를 종합 분석하여 투자 추천 리포트를 작성하세요.

## 현재 포트폴리오
{json.dumps(current_portfolio, ensure_ascii=False, indent=2)}

## 수학적 최적화 결과 (Mean-Variance 기반)
{json.dumps(optimization_result, ensure_ascii=False, indent=2)}

## 뉴스/시장 감성 분석
{json.dumps(news_analysis, ensure_ascii=False, indent=2)}

## 거시경제 지표
{json.dumps(macro_data, ensure_ascii=False, indent=2)}

## 추가 투자 예산
{budget:,.0f}원

다음 형식으로 리포트를 작성하세요:

1. **시장 환경 요약**: 현재 거시 환경과 시장 전망 (2~3문장)
2. **포트폴리오 진단**: 현재 포트폴리오의 강점/약점
3. **최적화 추천**: 수학적 최적화 결과에 뉴스/시장 상황을 반영한 조정 의견
4. **구체적 매수 가이드**: 예산 {budget:,.0f}원으로 어떤 종목을 몇 주 매수할지
5. **리스크 요인**: 주의해야 할 리스크와 대응 방안
6. **신뢰도 평가**: 이 추천의 신뢰 수준 (high/medium/low)과 그 이유

⚠️ 중요: 이 추천은 참고용이며, 최종 투자 결정은 사용자 본인이 해야 합니다.
투자에는 원금 손실 위험이 있습니다."""

        return self.llm.generate(
            prompt,
            system="당신은 경험 많은 포트폴리오 매니저입니다. 데이터에 기반한 객관적 분석과 실행 가능한 추천을 제공합니다.",
            max_tokens=3000,
        )
