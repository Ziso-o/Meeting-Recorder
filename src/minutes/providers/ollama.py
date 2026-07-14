"""OllamaProvider — 로컬 LLM (민감/B2G 회의, profile=secure).

네트워크가 로컬 Ollama 서버(기본 http://localhost:11434)로만 나간다.
httpx는 지연 임포트하여 테스트(mock 사용)에서는 불필요하게 요구하지 않는다.
"""

from __future__ import annotations


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen2.5:14b",
        timeout: float = 600.0,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        import httpx  # 지연 임포트

        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if system:
            payload["system"] = system

        resp = httpx.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("response", "")
