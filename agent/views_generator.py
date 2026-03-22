import json
from agent.llm_client import LLMClient

class ViewsGeneratorAgent:
    """Black-Litterman 모델용 투자자 뷰 생성 (LLM 기반)"""

    def __init__(self):
        self.llm = LLMClient()

    def generate_views(
        self,
        tickers: list[str],
        news_analysis: dict,
        macro_data: dict,
    ) -> dict:
        """각 종목의 기대 초과수익률 뷰를 생성

        Returns: {"AAPL": 0.05, "005930": -0.02, ...} (연율화 기대수익률)
        """
        prompt = f"""당신은 퀀트 애널리스트입니다.

아래 정보를 바탕으로 각 종목의 향후 6개월 기대 초과수익률을 추정하세요.

## 분석 대상 종목
{json.dumps(tickers, ensure_ascii=False)}

## 뉴스/시장 감성 분석
{json.dumps(news_analysis, ensure_ascii=False, indent=2)}

## 거시경제 지표
{json.dumps(macro_data, ensure_ascii=False, indent=2)}

아래 JSON 형식으로 응답하세요. 각 값은 -0.3 ~ 0.3 범위의 연율화 기대 초과수익률입니다:
{{
    "views": {{
        "TICKER": 0.05
    }},
    "confidence": {{
        "TICKER": 0.5
    }},
    "reasoning": "간단한 근거"
}}"""

        response = self.llm.generate_json(
            prompt,
            system="당신은 정량적 투자 분석가입니다. 데이터 기반으로 보수적인 수익률 전망을 제공합니다.",
            model_tier="light",
        )

        try:
            result = json.loads(response)
            return result
        except json.JSONDecodeError:
            return {
                "views": {t: 0.0 for t in tickers},
                "confidence": {t: 0.1 for t in tickers},
                "reasoning": "분석 실패 - 기본값 사용",
                "parse_error": True,
            }
