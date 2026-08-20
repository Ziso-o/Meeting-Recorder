"""전사 서브패키지 — ASR 엔진 + 화자분리 + 병합 + 팩토리.

엔진 선택 (환경변수 ASR_ENGINE):
  - "auto"           : GPU 있으면 faster-whisper, 없으면 Groq 폴백 (기본)
  - "faster-whisper" : 로컬 강제
  - "groq"           : 클라우드 폴백 강제
  - "mock"           : 오프라인/테스트
"""

from __future__ import annotations

import os
import sys

from .base import ASREngine, ASRSegment, Diarizer, SpeakerTurn
from .merge import merge_segments

__all__ = [
    "ASREngine",
    "Diarizer",
    "ASRSegment",
    "SpeakerTurn",
    "merge_segments",
    "select_asr_engine",
    "select_diarizer",
    "resolve_asr_choice",
    "gpu_available",
]


def gpu_available() -> bool:
    try:
        import torch  # 지연 임포트

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def resolve_asr_choice(choice: str | None = None) -> str:
    """엔진 이름 문자열을 결정한다(인스턴스화 없이 — 테스트 가능).

    무료·로컬 정책: `auto`는 **항상 로컬 faster-whisper**로 해석한다.
    GPU가 없으면 faster-whisper가 CPU로 동작한다(무료·로컬 유지).
    클라우드(Groq)는 `ASR_ENGINE=groq`로 **명시**했을 때만 사용한다.
    """
    choice = (choice if choice is not None else os.environ.get("ASR_ENGINE", "auto")).lower()
    if choice == "auto":
        return "faster-whisper"
    return choice


def select_asr_engine() -> ASREngine:
    choice = resolve_asr_choice()

    if choice == "mock":
        from .mock import MockASREngine

        return MockASREngine()

    if choice == "faster-whisper":
        from .whisper_engine import FasterWhisperEngine

        def _int(key: str) -> int:
            try:
                return max(0, int(os.environ.get(key, "0")))
            except ValueError:
                return 0

        return FasterWhisperEngine(
            model_size=os.environ.get("WHISPER_MODEL", "large-v3"),
            device=os.environ.get("WHISPER_DEVICE", "auto"),   # cuda | cpu | auto
            compute_type=os.environ.get("WHISPER_COMPUTE_TYPE", "auto"),
            beam_size=_int("WHISPER_BEAM_SIZE"),      # 0 → CPU는 1, GPU는 5
            cpu_threads=_int("WHISPER_CPU_THREADS"),  # 0 → CTranslate2 기본
            batch_size=_int("WHISPER_BATCH_SIZE"),    # 0 → 배치 추론 끔
        )

    if choice == "groq":
        from .groq_engine import GroqEngine

        return GroqEngine(api_key=os.environ.get("GROQ_API_KEY", ""))

    raise ValueError(f"지원하지 않는 ASR_ENGINE: {choice!r}")


def select_diarizer() -> Diarizer | None:
    """화자분리기 선택. DIARIZER=off면 비활성(단일 화자로 처리).

    무료·로컬 정책: `auto`인데 HF_TOKEN이 없으면 크래시 대신 **화자분리 비활성**으로
    graceful degrade(단일 화자). 화자분리를 강제하려면 `DIARIZER=pyannote`.
    """
    choice = os.environ.get("DIARIZER", "auto").lower()

    if choice in ("off", "none"):
        return None
    if choice == "mock":
        from .mock import MockDiarizer

        return MockDiarizer()

    hf_token = os.environ.get("HF_TOKEN", "")
    if choice == "auto" and not hf_token:
        print(
            "경고: HF_TOKEN이 없어 화자분리를 비활성화합니다(단일 화자). "
            "화자분리가 필요하면 HF_TOKEN 설정 후 DIARIZER=pyannote.",
            file=sys.stderr,
        )
        return None

    from .diarize import PyannoteDiarizer

    return PyannoteDiarizer(hf_token=hf_token)
