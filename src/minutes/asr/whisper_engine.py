"""FasterWhisperEngine — 로컬 전사 (faster-whisper large-v3).

GPU가 있으면 이 엔진을 우선 사용한다. glossary를 initial_prompt로 주입해
고유명사 인식률을 높인다. faster_whisper는 지연 임포트한다.
"""

from __future__ import annotations

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

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # 지연 임포트

            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        return self._model

    def transcribe(self, wav_path: str, initial_prompt: str = "") -> list[ASRSegment]:
        model = self._load()
        segments, _info = model.transcribe(
            wav_path,
            language=self.language,
            initial_prompt=initial_prompt or None,
            vad_filter=True,
            word_timestamps=False,
        )
        return [
            ASRSegment(start=float(s.start), end=float(s.end), text=s.text.strip())
            for s in segments
        ]
