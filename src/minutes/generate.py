"""Phase 1 — 회의록 생성기 CLI (텍스트 → 회의록).

사용법:
    python -m minutes.generate --input transcript.json --profile internal|secure

입력: 화자 라벨 전사 JSON. 두 형태를 지원한다.
    1) [{"speaker","start","end","text"}, ...]
    2) {"meta": {...}, "segments": [ ... 위 형태 ... ]}

출력: <stem>.minutes.json + <stem>.minutes.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .chain import generate_minutes
from .config import load_dotenv, provider_for_profile
from .glossary import load_glossary
from .render import render_markdown
from .schema import Segment


def _load_input(path: Path) -> tuple[list[Segment], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        raw_segments = data.get("segments", [])
        meta = data.get("meta", {})
    else:
        raw_segments = data
        meta = {}
    segments = [Segment.model_validate(s) for s in raw_segments]
    return segments, meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minutes.generate", description="회의록 생성기")
    parser.add_argument("--input", "-i", required=True, help="전사 JSON 경로")
    parser.add_argument(
        "--profile",
        "-p",
        choices=("internal", "secure"),
        default="internal",
        help="보안 프로파일: internal(Gemini) | secure(Ollama)",
    )
    parser.add_argument("--glossary", "-g", default="glossary.yaml", help="용어집 경로")
    parser.add_argument("--out", "-o", default=None, help="출력 파일 stem (기본: 입력 파일명)")
    args = parser.parse_args(argv)

    load_dotenv()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"입력 파일이 없습니다: {in_path}", file=sys.stderr)
        return 1

    segments, meta = _load_input(in_path)
    glossary = load_glossary(args.glossary)
    provider = provider_for_profile(args.profile)

    print(f"[profile={args.profile}] provider={provider.name}, segments={len(segments)}")
    minutes = generate_minutes(segments, provider, glossary=glossary, meta=meta)

    stem = Path(args.out) if args.out else in_path.with_suffix("")
    json_path = stem.with_suffix(".minutes.json")
    md_path = stem.with_suffix(".minutes.md")
    if str(json_path.parent) not in ("", "."):
        json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(minutes.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(render_markdown(minutes), encoding="utf-8")

    print(f"✓ {json_path}")
    print(f"✓ {md_path}")
    print(
        f"  결정 {len(minutes.decisions)}건, 액션 {len(minutes.action_items)}건, "
        f"미결 {len(minutes.open_issues)}건"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
