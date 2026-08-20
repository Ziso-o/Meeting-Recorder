"""LLM 프로바이더 공통 인터페이스."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """모든 LLM 어댑터가 구현해야 하는 최소 인터페이스.

    config로 프로바이더를 전환해도 체인 코드는 이 인터페이스만 알면 된다.
    """

    name: str

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int | None = None
    ) -> str:
        """프롬프트를 받아 모델 응답 텍스트를 반환한다.

        max_tokens: 이 호출의 출력 상한. 단계마다 필요한 길이가 다르다 —
          구간 요약은 짧아야 하고(길면 요약이 아니다), 통합 JSON은 길어도 된다.
          None이면 프로바이더 기본값.
        """
        ...
