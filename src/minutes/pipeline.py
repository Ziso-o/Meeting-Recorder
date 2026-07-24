"""Phase 3 — 결합 파이프라인 (오디오 → 회의록, 한 번에).

Phase 2(전사)와 Phase 1(회의록 생성)을 잇는다. n8n은 이 CLI(또는 두 하위 CLI)를
호출만 한다.

사용법:
    python -m minutes.pipeline --audio meeting.m4a --profile internal|secure

산출물: <stem>.transcript.json, <stem>.minutes.json, <stem>.minutes.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .chain import generate_minutes
from .config import load_dotenv, provider_for_profile
from .glossary import load_glossary
from .render import render_markdown
from .transcribe import transcribe_audio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minutes.pipeline", description="오디오→회의록 파이프라인")
    parser.add_argument("--audio", "-a", required=True, help="오디오 파일 경로")
    parser.add_argument(
        "--profile", "-p", choices=("internal", "secure"), default="internal",
        help="보안 프로파일: internal(Gemini) | secure(Ollama)",
    )
    parser.add_argument("--glossary", "-g", default="glossary.yaml", help="용어집 경로")
    parser.add_argument("--out", "-o", default=None, help="출력 stem (기본: 오디오 파일명)")
    parser.add_argument("--title", default="", help="회의 제목")
    parser.add_argument("--date", default="", help="회의 일자(YYYY-MM-DD)")
    parser.add_argument("--keep-wav", action="store_true", help="16k wav 유지")
    args = parser.parse_args(argv)

    load_dotenv()

    audio = Path(args.audio)
    if not audio.exists() and os.environ.get("ASR_ENGINE", "").lower() != "mock":
        print(f"오디오 파일이 없습니다: {audio}", file=sys.stderr)
        return 1

    stem = Path(args.out) if args.out else audio.with_suffix("")
    glossary = load_glossary(args.glossary)

    # 1) 전사 (Phase 2)
    print(f"[1/2] 전사: {audio.name} [profile={args.profile}]")
    segments = transcribe_audio(audio, args.glossary, keep_wav=args.keep_wav)
    meta = {"meeting_title": args.title, "date": args.date, "source_audio": audio.name}
    transcript_doc = {
        "meta": {k: v for k, v in meta.items() if v},
        "segments": [s.model_dump() for s in segments],
    }
    transcript_path = stem.with_suffix(".transcript.json")
    if str(transcript_path.parent) not in ("", "."):
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps(transcript_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ✓ {transcript_path} (세그먼트 {len(segments)}개)")

    # 2) 회의록 생성 (Phase 1) — 보안 프로파일이 LLM 프로바이더를 결정
    print(f"[2/2] 회의록 생성: provider by profile={args.profile}")
    provider = provider_for_profile(args.profile)
    minutes = generate_minutes(segments, provider, glossary=glossary, meta=meta)

    json_path = stem.with_suffix(".minutes.json")
    md_path = stem.with_suffix(".minutes.md")
    json_path.write_text(
        json.dumps(minutes.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(render_markdown(minutes), encoding="utf-8")
    print(f"  ✓ {json_path}")
    print(f"  ✓ {md_path}")
    print(
        f"  결정 {len(minutes.decisions)}건, 액션 {len(minutes.action_items)}건, "
        f"미결 {len(minutes.open_issues)}건"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
