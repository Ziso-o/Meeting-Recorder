"""FasterWhisperEngine — 로컬 전사 (faster-whisper large-v3).

GPU가 있으면 이 엔진을 우선 사용한다. glossary를 initial_prompt로 주입해
고유명사 인식률을 높인다. faster_whisper는 지연 임포트한다.
"""

from __future__ import annotations

from collections.abc import Callable

from .base import ASRSegment


class FasterWhisperEngine:
    name = "faster-whisper"

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "ko",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None

    def load(self):
        """모델 준비 — 캐시에 없으면 여기서 다운로드가 일어난다(large-v3 약 3GB)."""
        if self._model is None:
            from faster_whisper import WhisperModel  # 지연 임포트

            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        return self._model

    def transcribe(
        self,
        wav_path: str,
        initial_prompt: str = "",
        on_progress: Callable[[float, float], None] | None = None,
    ) -> list[ASRSegment]:
        """전사. on_progress(처리된_오디오초, 전체_오디오초)로 진행률을 알린다.

        faster-whisper 는 세그먼트를 **생성기로 하나씩** 내놓고 각 세그먼트에
        오디오 내 타임스탬프가 있다. 이를 소비하면서 알리면 정확한 진행률이 나온다
        (리스트로 한 번에 삼키면 이 정보가 버려진다).
        """
        model = self.load()
        segments, info = model.transcribe(
            wav_path,
            language=self.language,
            initial_prompt=initial_prompt or None,
            vad_filter=True,
            word_timestamps=False,
        )
        total = float(getattr(info, "duration", 0.0) or 0.0)
        out: list[ASRSegment] = []
        for s in segments:
            out.append(ASRSegment(start=float(s.start), end=float(s.end), text=s.text.strip()))
            if on_progress:
                on_progress(float(s.end), total)
        if on_progress and total:
            on_progress(total, total)  # 끝의 무음 구간까지 포함해 100%로 마감
        return out
