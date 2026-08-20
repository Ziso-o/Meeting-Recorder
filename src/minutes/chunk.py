"""전사 세그먼트를 시간/길이 단위 청크로 분할한다.

기본: 30분(1800초) 창. 단, 한 청크가 max_chars를 넘으면 그 전에 끊어
토큰 한계를 넘지 않게 한다(한국어 대략 1토큰≈2~3자 기준 보수적으로).
"""

from __future__ import annotations

from .schema import Segment

DEFAULT_WINDOW_SEC = 1800.0  # 30분
DEFAULT_MAX_CHARS = 6000


def _split_oversized(segments: list[Segment], max_chars: int) -> list[Segment]:
    """세그먼트 하나가 상한보다 길면 그 안에서도 쪼갠다.

    청크 분할은 세그먼트 **사이**에서만 일어나므로, 거대한 세그먼트가 하나 들어오면
    (화자분리 없이 통째로 병합된 경우 등) 분할이 통째로 무력화된다. 여기서 막는다.
    """
    out: list[Segment] = []
    for seg in segments:
        if len(seg.text) <= max_chars:
            out.append(seg)
            continue
        words = seg.text.split()
        pieces: list[str] = []
        buf = ""
        for w in words:
            if buf and len(buf) + 1 + len(w) > max_chars:
                pieces.append(buf)
                buf = w
            else:
                buf = f"{buf} {w}".strip()
        if buf:
            pieces.append(buf)
        # 시간은 글자 수 비율로 나눠 준다(근사 — 순서와 총 구간은 보존).
        span = max(0.0, seg.end - seg.start)
        total = sum(len(x) for x in pieces) or 1
        t = seg.start
        for piece in pieces:
            dt = span * (len(piece) / total)
            out.append(Segment(speaker=seg.speaker, start=t, end=t + dt, text=piece))
            t += dt
    return out


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

    for seg in _split_oversized(segments, max_chars):
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
