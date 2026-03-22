import json
from agent.llm_client import LLMClient

class FundamentalAnalystAgent:
    """재무제표 기반 펀더멘탈 분석 에이전트"""

    def __init__(self):
        self.llm = LLMClient()

    def analyze(
        self,
        ticker: str,
        name: str,
        financials: dict,
        stock_info: dict,
    ) -> str:
        """재무제표 데이터를 분석하여 펀더멘탈 평가 리포트 생성"""
        prompt = f"""당신은 주식 펀더멘탈 분석가입니다.

아래 재무 데이터를 분석하여 {name}({ticker})의 투자 매력도를 평가하세요.

## 기업 정보
{json.dumps(stock_info, ensure_ascii=False, indent=2, default=str)}

## 재무제표 데이터
{json.dumps(financials, ensure_ascii=False, indent=2, default=str)}

다음 항목을 포함하여 분석하세요:
1. **밸류에이션 평가**: P/E, P/B 등 기반 적정가치 판단
2. **수익성 분석**: ROE, 영업이익률, 순이익 추이
3. **재무 건전성**: 부채비율, 유동비율
4. **성장성**: 매출/이익 성장률 추이
5. **종합 의견**: 매수/보유/매도 의견과 근거

⚠️ 이 분석은 참고용이며, 투자 결정의 책임은 사용자에게 있습니다."""

        return self.llm.generate(
            prompt,
            system="당신은 경험 많은 주식 애널리스트입니다. 재무 데이터에 기반한 객관적 분석을 제공합니다.",
            max_tokens=2000,
            model_tier="heavy",
        )
