"""Phase 2 — 전사 엔진 CLI (오디오 → 화자라벨 텍스트).

사용법:
    python -m minutes.transcribe --audio meeting.m4a

파이프라인:
    ffmpeg(16kHz mono wav) → ASR(faster-whisper / Groq 폴백, initial_prompt에 glossary 주입)
    → pyannote 화자분리 → 세그먼트 병합 → Phase 1 입력 JSON 스키마로 출력.

출력: <stem>.transcript.json  ( {"meta": {...}, "segments": [{speaker,start,end,text}, ...]} )
그대로 `minutes.generate --input <stem>.transcript.json` 에 넘길 수 있다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .asr import merge_segments, select_asr_engine, select_diarizer
from .asr.audio import to_wav_16k_mono
from .config import load_dotenv
from .glossary import glossary_terms, load_glossary
from .schema import Segment


def transcribe_audio(
    audio: str | Path,
    glossary_path: str | Path = "glossary.yaml",
    keep_wav: bool = False,
) -> list[Segment]:
    """오디오 → 화자 라벨 세그먼트(Phase 1 입력 스키마). 파이프라인/CLI 공용.

    엔진/화자분리기 선택은 환경변수(ASR_ENGINE, DIARIZER)를 따른다.
    """
    audio = Path(audio)
    glossary = load_glossary(glossary_path)
    initial_prompt = glossary_terms(glossary)

    engine = select_asr_engine()
    diarizer = select_diarizer()
    print(f"ASR={engine.name}, diarizer={diarizer.name if diarizer else 'off'}")

    if engine.name == "mock":
        wav = str(audio)
        wav_to_clean = None
    else:
        wav = str(to_wav_16k_mono(audio))
        wav_to_clean = None if keep_wav else wav

    try:
        asr_segments = engine.transcribe(wav, initial_prompt=initial_prompt)
        turns = diarizer.diarize(wav) if diarizer else []
        return merge_segments(asr_segments, turns)
    finally:
        if wav_to_clean and Path(wav_to_clean).exists():
            Path(wav_to_clean).unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minutes.transcribe", description="전사 엔진")
    parser.add_argument("--audio", "-a", required=True, help="오디오 파일 경로 (m4a/mp3/wav...)")
    parser.add_argument("--glossary", "-g", default="glossary.yaml", help="용어집 경로")
    parser.add_argument("--out", "-o", default=None, help="출력 stem (기본: 오디오 파일명)")
    parser.add_argument("--title", default="", help="회의 제목(메타)")
    parser.add_argument("--date", default="", help="회의 일자(메타, YYYY-MM-DD)")
    parser.add_argument(
        "--keep-wav", action="store_true", help="변환된 16k wav를 삭제하지 않고 유지"
    )
    args = parser.parse_args(argv)

    load_dotenv()

    audio = Path(args.audio)
    if not audio.exists() and os.environ.get("ASR_ENGINE", "").lower() != "mock":
        print(f"오디오 파일이 없습니다: {audio}", file=sys.stderr)
        return 1

    segments = transcribe_audio(audio, args.glossary, keep_wav=args.keep_wav)

    meta = {"meeting_title": args.title, "date": args.date, "source_audio": audio.name}
    out_doc = {
        "meta": {k: v for k, v in meta.items() if v},
        "segments": [s.model_dump() for s in segments],
    }

    stem = Path(args.out) if args.out else audio.with_suffix("")
    out_path = stem.with_suffix(".transcript.json")
    out_path.write_text(json.dumps(out_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    speakers = sorted({s.speaker for s in segments})
    print(f"✓ {out_path}")
    print(f"  세그먼트 {len(segments)}개, 화자 {len(speakers)}명 {speakers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
