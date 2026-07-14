"""Vexa 전사 응답 → 우리 Segment 스키마(Phase 1 입력) 변환.

Vexa 전사 포맷은 버전에 따라 필드가 조금씩 다르므로 방어적으로 파싱한다.
"""

from __future__ import annotations

from typing import Any

from ..schema import Segment


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def vexa_to_segments(payload: dict[str, Any]) -> list[Segment]:
    """Vexa 전사 payload에서 세그먼트를 추출해 Segment 리스트로 변환."""
    segs = payload.get("segments")
    if segs is None and isinstance(payload.get("data"), dict):
        segs = payload["data"].get("segments")
    segs = segs or []

    result: list[Segment] = []
    for s in segs:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        speaker = str(s.get("speaker") or s.get("speaker_id") or "SPEAKER_00")
        start = _to_float(s.get("start", s.get("start_time", s.get("absolute_start_time"))))
        end = _to_float(s.get("end", s.get("end_time", s.get("absolute_end_time"))), start)
        result.append(Segment(speaker=speaker, start=start, end=end, text=text))
    return result
