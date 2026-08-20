"""오프라인/테스트용 mock 엔진 — GPU·네트워크·오디오 없이 파이프라인을 검증한다."""

from __future__ import annotations

from collections.abc import Callable

from .base import ASRSegment, SpeakerTurn


class MockASREngine:
    name = "mock"

    def load(self) -> None:
        return None

    def transcribe(
        self,
        wav_path: str,
        initial_prompt: str = "",
        on_progress: Callable[[float, float], None] | None = None,
    ) -> list[ASRSegment]:
        out = [
            ASRSegment(start=0.0, end=3.0, text="안녕하세요 회의를 시작하겠습니다"),
            ASRSegment(start=3.0, end=6.0, text="네 자료 공유드리겠습니다"),
            ASRSegment(start=6.0, end=9.0, text="그럼 다음 주까지 초안 작성하겠습니다"),
        ]
        for seg in out:  # 실제 엔진과 같은 방식으로 진행률을 알린다
            if on_progress:
                on_progress(seg.end, 9.0)
        return out


class MockDiarizer:
    name = "mock"

    def diarize(self, wav_path: str) -> list[SpeakerTurn]:
        return [
            SpeakerTurn(speaker="SPEAKER_00", start=0.0, end=3.2),
            SpeakerTurn(speaker="SPEAKER_01", start=3.0, end=6.1),
            SpeakerTurn(speaker="SPEAKER_00", start=6.0, end=9.0),
        ]
