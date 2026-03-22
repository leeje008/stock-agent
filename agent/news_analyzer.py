import json

from agent.llm_client import LLMClient


class NewsAnalystAgent:
    """뉴스 기사를 분석하여 시장 감성 및 종목 영향도를 평가"""

    def __init__(self):
        self.llm = LLMClient()

    def analyze_news(
        self,
        news_articles: list[dict],
        portfolio_tickers: list[str],
    ) -> dict:
        """
        news_articles: [{"title": "...", "summary": "...", "source": "...", "date": "..."}]
        portfolio_tickers: ["AAPL", "005930", "QQQ", ...]
        """
        prompt = f"""당신은 전문 금융 뉴스 분석가입니다.

아래 뉴스 기사들을 분석하여 다음을 수행하세요:

1. **감성 분석**: 각 뉴스의 시장 영향을 긍정/중립/부정으로 분류
2. **관련 종목 매핑**: 뉴스가 영향을 미칠 포트폴리오 종목 식별
3. **리스크 이벤트 감지**: 급락/급등 가능성이 있는 이벤트 식별
4. **종합 시장 전망**: 현재 시장 분위기 요약

현재 포트폴리오 종목: {portfolio_tickers}

뉴스 기사 목록:
{json.dumps(news_articles, ensure_ascii=False, indent=2)}

아래 JSON 형식으로 응답하세요:
{{
    "market_sentiment": "bullish|neutral|bearish",
    "sentiment_score": -1.0 ~ 1.0,
    "key_events": [
        {{
            "event": "이벤트 설명",
            "impact": "positive|negative|neutral",
            "affected_tickers": ["AAPL"],
            "severity": "high|medium|low"
        }}
    ],
    "ticker_sentiments": {{
        "TICKER": {{"score": 0.0, "reason": "..."}}
    }},
    "summary": "종합 시장 전망 요약"
}}"""

        response = self.llm.generate_json(
            prompt,
            system="당신은 전문 금융 뉴스 분석가입니다. 객관적이고 데이터 기반의 분석을 제공합니다.",
            model_tier="light",
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "market_sentiment": "neutral",
                "sentiment_score": 0.0,
                "key_events": [],
                "ticker_sentiments": {},
                "summary": response,
                "parse_error": True,
            }
