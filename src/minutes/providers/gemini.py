"""GeminiProvider — 클라우드 LLM 무료티어 (내부 회의, profile=internal).

⚠️ 클라우드로 회의 내용이 전송된다. B2G 민감 회의에는 사용하지 말 것(profile=secure는 Ollama).
API 키는 .env(GEMINI_API_KEY)에서만 읽는다. 코드 하드코딩 금지.
httpx는 지연 임포트한다.
"""

from __future__ import annotations


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY가 없습니다. .env를 확인하세요.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        import httpx  # 지연 임포트

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        body: dict = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        resp = httpx.post(
            url,
            params={"key": self.api_key},
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
