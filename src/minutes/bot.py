"""Phase 4 — Vexa 봇 제어 CLI.

n8n(또는 사람)이 호출한다. 봇 참석 요청 / 전사 조회 / 종료 / 인제스트(전사→회의록).

사용법:
    python -m minutes.bot request   --platform google_meet --meeting abc-defg-hij
    python -m minutes.bot transcript --platform google_meet --meeting abc-defg-hij --out mtg
    python -m minutes.bot stop      --platform google_meet --meeting abc-defg-hij
    python -m minutes.bot ingest    --platform google_meet --meeting abc-defg-hij \
                                    --profile internal --out mtg
      → Vexa 전사 조회 → Segment 변환 → 회의록 생성(mtg.minutes.json/.md, mtg.transcript.json)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .chain import generate_minutes
from .config import load_dotenv, provider_for_profile
from .glossary import load_glossary
from .render import render_markdown
from .vexa import select_vexa_client, vexa_to_segments


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_request(args) -> int:
    client = select_vexa_client()
    print(f"봇 참석 요청: name={client.bot_name}, {args.platform}/{args.meeting}")
    _print(client.request_bot(args.platform, args.meeting, language=args.language))
    return 0


def cmd_stop(args) -> int:
    client = select_vexa_client()
    _print(client.stop_bot(args.platform, args.meeting))
    return 0


def cmd_transcript(args) -> int:
    client = select_vexa_client()
    payload = client.get_transcript(args.platform, args.meeting)
    if args.out:
        out = Path(args.out).with_suffix(".vexa.json")
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ {out}")
    else:
        _print(payload)
    return 0


def cmd_ingest(args) -> int:
    """Vexa 전사 → Segment 변환 → 회의록 생성(Phase 1 재사용)."""
    client = select_vexa_client()
    payload = client.get_transcript(args.platform, args.meeting)
    segments = vexa_to_segments(payload)
    if not segments:
        print("경고: Vexa 전사에서 세그먼트를 찾지 못했습니다.")
        return 2

    glossary = load_glossary(args.glossary)
    meta = {"meeting_title": args.title, "date": args.date, "source": f"vexa:{args.meeting}"}

    stem = Path(args.out) if args.out else Path(args.meeting)
    transcript_doc = {
        "meta": {k: v for k, v in meta.items() if v},
        "segments": [s.model_dump() for s in segments],
    }
    stem.with_suffix(".transcript.json").write_text(
        json.dumps(transcript_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    provider = provider_for_profile(args.profile)
    minutes = generate_minutes(segments, provider, glossary=glossary, meta=meta)
    stem.with_suffix(".minutes.json").write_text(
        json.dumps(minutes.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    stem.with_suffix(".minutes.md").write_text(render_markdown(minutes), encoding="utf-8")

    print(f"✓ {stem}.transcript.json / .minutes.json / .minutes.md")
    print(f"  세그먼트 {len(segments)}개, 결정 {len(minutes.decisions)}건, 액션 {len(minutes.action_items)}건")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="minutes.bot", description="Vexa 봇 제어")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--platform", default="google_meet", help="회의 플랫폼")
        p.add_argument("--meeting", "-m", required=True, help="회의 ID(native_meeting_id)")

    p_req = sub.add_parser("request", help="봇 참석 요청")
    add_common(p_req)
    p_req.add_argument("--language", default="ko")
    p_req.set_defaults(func=cmd_request)

    p_stop = sub.add_parser("stop", help="봇 종료")
    add_common(p_stop)
    p_stop.set_defaults(func=cmd_stop)

    p_tr = sub.add_parser("transcript", help="Vexa 전사 조회")
    add_common(p_tr)
    p_tr.add_argument("--out", "-o", default=None)
    p_tr.set_defaults(func=cmd_transcript)

    p_in = sub.add_parser("ingest", help="Vexa 전사 → 회의록 생성")
    add_common(p_in)
    p_in.add_argument("--profile", "-p", choices=("internal", "secure"), default="internal")
    p_in.add_argument("--glossary", "-g", default="glossary.yaml")
    p_in.add_argument("--out", "-o", default=None)
    p_in.add_argument("--title", default="")
    p_in.add_argument("--date", default="")
    p_in.set_defaults(func=cmd_ingest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
