"""A/B 비교 — Vexa 내장 전사 vs 우리 Phase 2 전사.

두 전사의 텍스트를 비교한다. 정답(--ref)이 있으면 각각의 CER을 계산하고,
없으면 두 전사 간 상호 CER(불일치율)과 세그먼트/화자 통계를 낸다.

사용법:
    # 파일 비교 (Vexa 전사 json + 우리 transcript.json)
    python scripts/ab_transcribe.py --vexa mtg.vexa.json --ours mtg.transcript.json
    # 정답 대비 CER
    python scripts/ab_transcribe.py --vexa mtg.vexa.json --ours mtg.transcript.json --ref ref.txt
    # Vexa를 API로 바로 조회 (VEXA_CLIENT/env 사용)
    python scripts/ab_transcribe.py --platform google_meet --meeting abc --ours mtg.transcript.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# scripts/ 의 cer.py 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cer as cer_mod  # noqa: E402

# 패키지(src) 사용 — Vexa 조회/변환
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _segments_from_file(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("segments", [])
    return data


def _join_text(segments: list[dict]) -> str:
    return " ".join((s.get("text") or "").strip() for s in segments)


def _stats(name: str, segments: list[dict]) -> dict:
    speakers = sorted({str(s.get("speaker", "")) for s in segments if s.get("speaker")})
    text = _join_text(segments)
    return {
        "name": name,
        "segments": len(segments),
        "speakers": len(speakers),
        "chars": len(cer_mod.normalize(text)),
        "text": text,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ab_transcribe", description="Vexa vs Phase2 전사 A/B")
    ap.add_argument("--vexa", help="Vexa 전사 JSON 파일")
    ap.add_argument("--platform", default="google_meet", help="(파일 대신 API 조회 시) 플랫폼")
    ap.add_argument("--meeting", help="(파일 대신 API 조회 시) 회의 ID")
    ap.add_argument("--ours", required=True, help="우리 Phase 2 transcript.json")
    ap.add_argument("--ref", default=None, help="정답 텍스트 파일(선택)")
    args = ap.parse_args(argv)

    # Vexa 세그먼트 확보: 파일 우선, 없으면 API 조회
    if args.vexa:
        vexa_segments = _segments_from_file(args.vexa)
    elif args.meeting:
        from minutes.vexa import select_vexa_client, vexa_to_segments

        payload = select_vexa_client().get_transcript(args.platform, args.meeting)
        vexa_segments = [s.model_dump() for s in vexa_to_segments(payload)]
    else:
        print("오류: --vexa 파일 또는 --meeting(API) 중 하나가 필요합니다.", file=sys.stderr)
        return 1

    ours_segments = _segments_from_file(args.ours)

    a = _stats("Vexa 내장", vexa_segments)
    b = _stats("Phase 2(우리)", ours_segments)

    print("=" * 56)
    print(f"{'항목':<16}{'Vexa 내장':>18}{'Phase2(우리)':>20}")
    print("-" * 56)
    print(f"{'세그먼트 수':<16}{a['segments']:>18}{b['segments']:>20}")
    print(f"{'화자 수':<16}{a['speakers']:>18}{b['speakers']:>20}")
    print(f"{'문자 수':<16}{a['chars']:>18}{b['chars']:>20}")

    if args.ref:
        ref = Path(args.ref).read_text(encoding="utf-8")
        cer_a = cer_mod.cer(ref, a["text"])
        cer_b = cer_mod.cer(ref, b["text"])
        print(f"{'CER(정답대비)':<16}{cer_a * 100:>17.2f}%{cer_b * 100:>19.2f}%")
        winner = "Vexa 내장" if cer_a < cer_b else "Phase2(우리)"
        print("-" * 56)
        print(f"→ CER 우수: {winner}")
    else:
        cross = cer_mod.cer(a["text"], b["text"])
        print("-" * 56)
        print(f"두 전사 간 상호 불일치(CER): {cross * 100:.2f}%")
        print("(정답이 없어 우열 판정 불가 — --ref 로 정답을 주면 CER 비교 가능)")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
