"""OllamaProvider — 로컬 LLM (민감/B2G 회의, profile=secure).

네트워크가 로컬 Ollama 서버(기본 http://localhost:11434)로만 나간다.
httpx는 지연 임포트하여 테스트(mock 사용)에서는 불필요하게 요구하지 않는다.
"""

from __future__ import annotations

import os
import time


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen2.5:14b",
        timeout: float | None = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        # CPU 로컬 LLM은 느리다 — 기본을 넉넉히 두고 환경변수로 조정 가능하게.
        self.timeout = timeout if timeout is not None else float(
            os.environ.get("OLLAMA_TIMEOUT", "1800")
        )

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

        started = time.monotonic()
        try:
            resp = httpx.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.TimeoutException as e:
            # "timed out" 한 줄로는 무엇을 어떻게 고쳐야 할지 알 수 없다.
            raise TimeoutError(
                f"Ollama 응답이 {time.monotonic() - started:.0f}초 안에 오지 않았어요"
                f" (model={self.model}, host={self.host}, 입력 {len(prompt):,}자).\n"
                f"  · 더 작은 모델을 쓰세요: OLLAMA_MODEL=qwen2.5:7b (CPU면 3b)\n"
                f"  · 기다릴 수 있으면 OLLAMA_TIMEOUT을 늘리세요(현재 {self.timeout:.0f}초)"
            ) from e
        except httpx.HTTPError as e:
            raise RuntimeError(
                f"Ollama 호출 실패 (model={self.model}, host={self.host}): {e}"
            ) from e
        return resp.json().get("response", "")
