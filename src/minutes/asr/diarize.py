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
            import warnings

            import torch  # 지연 임포트

            # torchcodec 미사용(메모리 오디오로 우회)하므로 관련 경고 소음 제거
            warnings.filterwarnings("ignore", message=r".*torchcodec.*")
            warnings.filterwarnings("ignore", module=r"pyannote\.audio\.core\.io")
            from pyannote.audio import Pipeline

            try:
                # 최신 pyannote/huggingface_hub: token 인자
                pipe = Pipeline.from_pretrained(self.model, token=self.hf_token)
            except TypeError:
                # 구버전 호환: use_auth_token 인자
                pipe = Pipeline.from_pretrained(self.model, use_auth_token=self.hf_token)
            dev = self.device
            if dev == "auto":
                dev = "cuda" if torch.cuda.is_available() else "cpu"
            pipe.to(torch.device(dev))
            self._pipeline = pipe
        return self._pipeline

    def _load_audio(self, wav_path: str):
        """torchcodec 우회: soundfile로 wav를 메모리에 읽어 pyannote에 dict로 넘긴다.

        pyannote 파이프라인은 파일 경로 대신
        {"waveform": (channel, time) 텐서, "sample_rate": int} 를 받을 수 있다.
        이렇게 하면 torchcodec/ffmpeg 디코딩 경로를 완전히 건너뛴다.
        """
        import soundfile as sf
        import torch

        data, sr = sf.read(wav_path, dtype="float32", always_2d=True)  # (frames, channels)
        waveform = torch.from_numpy(data.T).contiguous()  # (channels, frames)
        return {"waveform": waveform, "sample_rate": int(sr)}

    def diarize(self, wav_path: str) -> list[SpeakerTurn]:
        pipeline = self._load()
        try:
            audio_in = self._load_audio(wav_path)
        except Exception:
            audio_in = wav_path  # soundfile 미설치 등 → 기존 경로 방식으로 폴백
        result = pipeline(audio_in)
        # pyannote 4.x는 DiarizeOutput 반환(.speaker_diarization가 Annotation),
        # 구버전은 Annotation을 직접 반환 → 둘 다 대응
        annotation = getattr(result, "speaker_diarization", result)
        turns: list[SpeakerTurn] = []
        for segment, _track, speaker in annotation.itertracks(yield_label=True):
            turns.append(
                SpeakerTurn(speaker=str(speaker), start=float(segment.start), end=float(segment.end))
            )
        turns.sort(key=lambda t: t.start)
        return turns
