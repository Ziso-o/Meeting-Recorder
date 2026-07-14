"""오프라인/테스트용 mock 엔진 — GPU·네트워크·오디오 없이 파이프라인을 검증한다."""

from __future__ import annotations

from .base import ASRSegment, SpeakerTurn


class MockASREngine:
    name = "mock"

    def transcribe(self, wav_path: str, initial_prompt: str = "") -> list[ASRSegment]:
        return [
            ASRSegment(start=0.0, end=3.0, text="안녕하세요 회의를 시작하겠습니다"),
            ASRSegment(start=3.0, end=6.0, text="네 자료 공유드리겠습니다"),
            ASRSegment(start=6.0, end=9.0, text="그럼 다음 주까지 초안 작성하겠습니다"),
        ]


class MockDiarizer:
    name = "mock"

    def diarize(self, wav_path: str) -> list[SpeakerTurn]:
        return [
            SpeakerTurn(speaker="SPEAKER_00", start=0.0, end=3.2),
            SpeakerTurn(speaker="SPEAKER_01", start=3.0, end=6.1),
            SpeakerTurn(speaker="SPEAKER_00", start=6.0, end=9.0),
        ]
