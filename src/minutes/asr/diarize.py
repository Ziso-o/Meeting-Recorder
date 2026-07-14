"""PyannoteDiarizer — 화자분리 (pyannote.audio 3.1).

HF 토큰(HF_TOKEN)이 필요하다(pyannote/speaker-diarization-3.1 게이트 모델).
pyannote/torch는 지연 임포트한다.
"""

from __future__ import annotations

from .base import SpeakerTurn


class PyannoteDiarizer:
    name = "pyannote"

    def __init__(
        self,
        hf_token: str,
        model: str = "pyannote/speaker-diarization-3.1",
        device: str = "auto",
    ) -> None:
        if not hf_token:
            raise ValueError("HF_TOKEN이 없습니다. pyannote 화자분리에 필요합니다.")
        self.hf_token = hf_token
        self.model = model
        self.device = device
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            import torch  # 지연 임포트
            from pyannote.audio import Pipeline

            pipe = Pipeline.from_pretrained(self.model, use_auth_token=self.hf_token)
            dev = self.device
            if dev == "auto":
                dev = "cuda" if torch.cuda.is_available() else "cpu"
            pipe.to(torch.device(dev))
            self._pipeline = pipe
        return self._pipeline

    def diarize(self, wav_path: str) -> list[SpeakerTurn]:
        pipeline = self._load()
        annotation = pipeline(wav_path)
        turns: list[SpeakerTurn] = []
        for segment, _track, speaker in annotation.itertracks(yield_label=True):
            turns.append(
                SpeakerTurn(speaker=str(speaker), start=float(segment.start), end=float(segment.end))
            )
        turns.sort(key=lambda t: t.start)
        return turns
