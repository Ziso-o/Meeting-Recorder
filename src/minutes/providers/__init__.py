"""LLM 프로바이더 어댑터 + 팩토리.

어댑터 패턴:
    - OllamaProvider  (로컬, 민감 회의 / profile=secure)
    - GeminiProvider  (클라우드 무료티어, 내부 회의 / profile=internal)
    - MockProvider    (테스트/오프라인)

config로 전환 가능하게 공통 인터페이스(LLMProvider.generate)를 정의한다.
"""

from __future__ import annotations

from .base import LLMProvider
from .gemini import GeminiProvider
from .mock import MockProvider
from .ollama import OllamaProvider

__all__ = ["LLMProvider", "OllamaProvider", "GeminiProvider", "MockProvider"]
