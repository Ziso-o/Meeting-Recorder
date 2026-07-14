"""Phase 2 — 전사 엔진 CLI (오디오 → 화자라벨 텍스트).

STUB — Phase 2에서 구현한다. 앞서가지 마라.

목표 인터페이스:
    python -m minutes.transcribe --audio meeting.m4a

파이프라인 (Phase 2에서 구현):
    ffmpeg(16kHz mono wav) → faster-whisper(initial_prompt에 glossary 주입)
    → pyannote 화자분리 → 세그먼트 병합 → Phase 1 입력 JSON 스키마로 출력.
    GPU 없으면 Groq API로 폴백.
"""


def main() -> None:
    raise NotImplementedError("Phase 2에서 구현 예정")


if __name__ == "__main__":
    main()
