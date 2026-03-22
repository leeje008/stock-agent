import re

from openai import OpenAI

from config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL_LIGHT, LLM_MODEL_HEAVY, LLM_MAX_TOKENS


class LLMClient:
    """Ollama 로컬 LLM 클라이언트 (OpenAI 호환 API)"""

    def __init__(self):
        self.client = OpenAI(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
        )
        self.model_light = LLM_MODEL_LIGHT
        self.model_heavy = LLM_MODEL_HEAVY
        self.max_tokens = LLM_MAX_TOKENS

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        model_tier: str = "heavy",
    ) -> str:
        model = self.model_light if model_tier == "light" else self.model_heavy
        temperature = 0.3 if model_tier == "light" else 0.5

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content

    def generate_json(
        self,
        prompt: str,
        system: str | None = None,
        model_tier: str = "light",
    ) -> str:
        """JSON 응답을 기대하는 호출 (기본: light 모델)"""
        full_system = (system or "") + "\n\n반드시 유효한 JSON으로만 응답하세요. 마크다운 코드블록이나 다른 텍스트를 포함하지 마세요."
        response = self.generate(
            prompt, system=full_system.strip(), model_tier=model_tier
        )
        return self._strip_code_fences(response)

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """로컬 모델이 JSON을 코드펜스로 감싸는 경우 제거"""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            return match.group(1).strip()
        return text
