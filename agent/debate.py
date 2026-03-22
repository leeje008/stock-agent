from agent.llm_client import LLMClient
import json


class DebateAgent:
    """Bull vs Bear 멀티 에이전트 토론 시스템"""

    def __init__(self):
        self.llm = LLMClient()

    def run_debate(
        self,
        portfolio_data: dict,
        news_analysis: dict,
        macro_data: dict,
    ) -> dict:
        """3라운드 토론 실행: Bull → Bear → Moderator

        Returns: {
            "bull_case": str,
            "bear_case": str,
            "synthesis": str,
            "final_verdict": "bullish" | "neutral" | "bearish",
        }
        """
        context = f"""## 포트폴리오 현황
{json.dumps(portfolio_data, ensure_ascii=False, indent=2, default=str)}

## 뉴스 분석
{json.dumps(news_analysis, ensure_ascii=False, indent=2, default=str)}

## 거시경제 지표
{json.dumps(macro_data, ensure_ascii=False, indent=2, default=str)}"""

        # Round 1: Bull Analyst
        bull_case = self.llm.generate(
            f"""아래 데이터를 바탕으로 현재 포트폴리오와 시장에 대해 **낙관적(강세)** 관점의 분석을 제시하세요.
긍정적 요소, 기회, 상승 가능성에 초점을 맞추세요.
3~5개 핵심 논거를 제시하세요.

{context}""",
            system="당신은 경험 많은 강세론자(Bull) 애널리스트입니다. 시장의 기회와 긍정적 요소를 찾는 것이 전문입니다.",
            max_tokens=1500,
            model_tier="heavy",
        )

        # Round 2: Bear Analyst
        bear_case = self.llm.generate(
            f"""아래 데이터를 바탕으로 현재 포트폴리오와 시장에 대해 **비관적(약세)** 관점의 분석을 제시하세요.
리스크, 위협, 하락 가능성에 초점을 맞추세요.
3~5개 핵심 논거를 제시하세요.

강세론자의 의견도 참고하되 반박하세요:
{bull_case[:500]}

{context}""",
            system="당신은 경험 많은 약세론자(Bear) 애널리스트입니다. 시장의 리스크와 위험 요소를 찾는 것이 전문입니다.",
            max_tokens=1500,
            model_tier="heavy",
        )

        # Round 3: Moderator Synthesis
        synthesis = self.llm.generate(
            f"""두 애널리스트의 의견을 종합하여 균형 잡힌 결론을 내리세요.

## 강세 의견
{bull_case}

## 약세 의견
{bear_case}

다음을 포함하세요:
1. 양측 의견 중 타당한 논거 정리
2. 현재 시장 상황에서 더 설득력 있는 쪽 판단
3. 최종 의견 (bullish/neutral/bearish)과 확신도 (0~100%)
4. 투자자가 주의해야 할 핵심 포인트""",
            system="당신은 중립적인 수석 애널리스트입니다. 양측 의견을 공정하게 평가하여 균형 잡힌 결론을 내립니다.",
            max_tokens=2000,
            model_tier="heavy",
        )

        # Extract verdict
        verdict = "neutral"
        synthesis_lower = synthesis.lower()
        if "bullish" in synthesis_lower or "강세" in synthesis_lower:
            verdict = "bullish"
        elif "bearish" in synthesis_lower or "약세" in synthesis_lower:
            verdict = "bearish"

        return {
            "bull_case": bull_case,
            "bear_case": bear_case,
            "synthesis": synthesis,
            "final_verdict": verdict,
        }
