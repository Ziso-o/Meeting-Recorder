"""FasterWhisperEngine — 로컬 전사 (faster-whisper large-v3).

GPU가 있으면 이 엔진을 우선 사용한다. glossary를 initial_prompt로 주입해
고유명사 인식률을 높인다. faster_whisper는 지연 임포트한다.
"""

from __future__ import annotations

from collections.abc import Callable

from .base import ASRSegment
from .info import CUDA_HELP, asr_device, quiet_hf_symlink_warning, register_cuda_dlls


def _is_cuda_library_error(e: Exception) -> bool:
    """CUDA 라이브러리를 못 찾아 죽은 것인지 — 그때만 설치 안내를 붙인다."""
    msg = str(e).lower()
    return any(k in msg for k in ("cublas", "cudnn", "cudart", "cuda"))


class FasterWhisperEngine:
    name = "faster-whisper"

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "ko",
        beam_size: int = 0,
        cpu_threads: int = 0,
        batch_size: int = 0,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size      # 0 = 디바이스에 맞춰 자동
        self.cpu_threads = cpu_threads  # 0 = CTranslate2 기본(코어 수)
        self.batch_size = batch_size    # 0 = 배치 추론 끔
        self._model = None
        self._pipeline = None

    def effective_beam_size(self) -> int:
        """빔 크기. CPU에서는 greedy(1)가 기본 — 품질 손해는 작고 1.5~2배 빠르다."""
        if self.beam_size > 0:
            return self.beam_size
        return 5 if asr_device() == "cuda" else 1

    def load(self):
        """모델 준비 — 캐시에 없으면 여기서 다운로드가 일어난다(large-v3 약 3GB)."""
        if self._model is None:
            from faster_whisper import WhisperModel  # 지연 임포트

            # pip 로 깔린 CUDA DLL 은 PATH 에 없다 — 여기서 찾아 등록한다.
            register_cuda_dlls()
            quiet_hf_symlink_warning()   # 무해한 Windows 경고가 진짜 오류를 가리지 않게
            try:
                self._model = WhisperModel(
                    self.model_size, device=self.device, compute_type=self.compute_type,
                    cpu_threads=self.cpu_threads,
                )
            except (RuntimeError, OSError) as e:
                if not _is_cuda_library_error(e):
                    raise
                raise RuntimeError(f"{e}\n\n{CUDA_HELP}") from e
            if self.batch_size > 0:
                # 배치 추론: VAD로 자른 구간을 묶어 한 번에 돌린다(faster-whisper 1.1+).
                try:
                    from faster_whisper import BatchedInferencePipeline

                    self._pipeline = BatchedInferencePipeline(model=self._model)
                except Exception as e:  # noqa: BLE001  구버전 등 — 일반 모드로 계속
                    print(f"  배치 추론을 쓸 수 없어 일반 모드로 진행합니다: {e}")
            print(f"  전사 설정: {self.model_size} · {asr_device()} · "
                  f"beam={self.effective_beam_size()} · "
                  f"batch={self.batch_size if self._pipeline else 'off'} · "
                  f"threads={self.cpu_threads or 'auto'}")
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
        opts = {
            "language": self.language,
            "initial_prompt": initial_prompt or None,
            "vad_filter": True,
            "word_timestamps": False,
            "beam_size": self.effective_beam_size(),
        }
        if self._pipeline is not None:
            segments, info = self._pipeline.transcribe(
                wav_path, batch_size=self.batch_size, **opts
            )
        else:
            segments, info = model.transcribe(wav_path, **opts)
        total = float(getattr(info, "duration", 0.0) or 0.0)
        out: list[ASRSegment] = []
        for s in segments:
            out.append(ASRSegment(start=float(s.start), end=float(s.end), text=s.text.strip()))
            if on_progress:
                on_progress(float(s.end), total)
        if on_progress and total:
            on_progress(total, total)  # 끝의 무음 구간까지 포함해 100%로 마감
        return out
