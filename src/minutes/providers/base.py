"""LLM 프로바이더 공통 인터페이스."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """모든 LLM 어댑터가 구현해야 하는 최소 인터페이스.

    config로 프로바이더를 전환해도 체인 코드는 이 인터페이스만 알면 된다.
    """

    name: str

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        """프롬프트를 받아 모델 응답 텍스트를 반환한다."""
        ...
