"""전사 세그먼트를 시간/길이 단위 청크로 분할한다.

기본: 30분(1800초) 창. 단, 한 청크가 max_chars를 넘으면 그 전에 끊어
토큰 한계를 넘지 않게 한다(한국어 대략 1토큰≈2~3자 기준 보수적으로).
"""

from __future__ import annotations

from .schema import Segment

DEFAULT_WINDOW_SEC = 1800.0  # 30분
DEFAULT_MAX_CHARS = 6000


def chunk_segments(
    segments: list[Segment],
    window_sec: float = DEFAULT_WINDOW_SEC,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[list[Segment]]:
    """세그먼트 리스트를 청크(세그먼트 리스트의 리스트)로 나눈다."""
    if not segments:
        return []

    chunks: list[list[Segment]] = []
    current: list[Segment] = []
    chunk_start = segments[0].start
    char_count = 0

    for seg in segments:
        over_time = current and (seg.end - chunk_start) > window_sec
        over_chars = current and (char_count + len(seg.text)) > max_chars
        if over_time or over_chars:
            chunks.append(current)
            current = []
            chunk_start = seg.start
            char_count = 0
        current.append(seg)
        char_count += len(seg.text)

    if current:
        chunks.append(current)
    return chunks


def render_segments(segments: list[Segment]) -> str:
    """세그먼트를 '[화자] 텍스트' 형태의 사람이 읽는 텍스트로 렌더링."""
    return "\n".join(f"[{s.speaker}] {s.text}" for s in segments)
