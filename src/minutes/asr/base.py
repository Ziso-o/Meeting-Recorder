"""전사 엔진 공통 타입/인터페이스."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ASRSegment(BaseModel):
    """ASR(음성인식) 출력 세그먼트 — 아직 화자 미지정."""

    start: float
    end: float
    text: str


class SpeakerTurn(BaseModel):
    """화자분리 출력 — 특정 화자가 말한 시간 구간."""

    speaker: str
    start: float
    end: float


@runtime_checkable
class ASREngine(Protocol):
    name: str

    def load(self) -> None:
        """모델을 준비한다(필요하면 다운로드). transcribe 전에 따로 부를 수 있다.

        느린 '모델 받는 중'과 '전사 중'을 호출자가 구분해 보여주기 위해 분리돼 있다.
        """
        ...

    def transcribe(self, wav_path: str, initial_prompt: str = "") -> list[ASRSegment]:
        """16kHz mono wav를 받아 세그먼트 리스트를 반환한다."""
        ...


@runtime_checkable
class Diarizer(Protocol):
    name: str

    def diarize(self, wav_path: str) -> list[SpeakerTurn]:
        """16kHz mono wav를 받아 화자 턴 리스트를 반환한다."""
        ...
