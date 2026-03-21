import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL, LLM_MAX_TOKENS


class LLMClient:
    """Anthropic Claude API 클라이언트 래퍼"""

    def __init__(self):
        if not ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
            )
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = LLM_MODEL
        self.max_tokens = LLM_MAX_TOKENS

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> str:
        """JSON 응답을 기대하는 호출"""
        full_system = (system or "") + "\n\n반드시 유효한 JSON으로만 응답하세요. 다른 텍스트를 포함하지 마세요."
        return self.generate(prompt, system=full_system.strip())
