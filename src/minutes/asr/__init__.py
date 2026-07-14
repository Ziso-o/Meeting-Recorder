"""전사 서브패키지 — ASR 엔진 + 화자분리 + 병합 + 팩토리.

엔진 선택 (환경변수 ASR_ENGINE):
  - "auto"           : GPU 있으면 faster-whisper, 없으면 Groq 폴백 (기본)
  - "faster-whisper" : 로컬 강제
  - "groq"           : 클라우드 폴백 강제
  - "mock"           : 오프라인/테스트
"""

from __future__ import annotations

import os

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
    "gpu_available",
]


def gpu_available() -> bool:
    try:
        import torch  # 지연 임포트

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def select_asr_engine() -> ASREngine:
    choice = os.environ.get("ASR_ENGINE", "auto").lower()

    if choice == "mock":
        from .mock import MockASREngine

        return MockASREngine()

    if choice == "auto":
        choice = "faster-whisper" if gpu_available() else "groq"

    if choice == "faster-whisper":
        from .whisper_engine import FasterWhisperEngine

        return FasterWhisperEngine(
            model_size=os.environ.get("WHISPER_MODEL", "large-v3"),
        )

    if choice == "groq":
        from .groq_engine import GroqEngine

        return GroqEngine(api_key=os.environ.get("GROQ_API_KEY", ""))

    raise ValueError(f"지원하지 않는 ASR_ENGINE: {choice!r}")


def select_diarizer() -> Diarizer | None:
    """화자분리기 선택. DIARIZER=off면 비활성(단일 화자로 처리)."""
    choice = os.environ.get("DIARIZER", "auto").lower()

    if choice in ("off", "none"):
        return None
    if choice == "mock":
        from .mock import MockDiarizer

        return MockDiarizer()

    from .diarize import PyannoteDiarizer

    return PyannoteDiarizer(hf_token=os.environ.get("HF_TOKEN", ""))
