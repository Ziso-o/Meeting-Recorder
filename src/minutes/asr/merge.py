"""ASR 세그먼트 + 화자 턴 → Phase 1 입력 스키마(Segment) 병합.

각 ASR 세그먼트에 가장 많이 겹치는 화자를 배정하고,
연속된 동일 화자 세그먼트를 병합해 읽기 좋은 발화 단위로 만든다.
"""

from __future__ import annotations

from ..schema import Segment
from .base import ASRSegment, SpeakerTurn


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speaker(seg: ASRSegment, turns: list[SpeakerTurn]) -> str:
    """세그먼트에 겹침이 가장 큰 화자를 배정. 겹침 없으면 가장 가까운 화자."""
    if not turns:
        return "SPEAKER_00"

    best_spk, best_ov = "", 0.0
    for t in turns:
        ov = _overlap(seg.start, seg.end, t.start, t.end)
        if ov > best_ov:
            best_ov, best_spk = ov, t.speaker

    if best_ov > 0:
        return best_spk

    # 겹침이 없으면 세그먼트 중심에 시간상 가장 가까운 턴.
    mid = (seg.start + seg.end) / 2
    nearest = min(
        turns,
        key=lambda t: 0.0 if t.start <= mid <= t.end else min(abs(mid - t.start), abs(mid - t.end)),
    )
    return nearest.speaker


def merge_segments(
    asr_segments: list[ASRSegment],
    turns: list[SpeakerTurn],
    merge_consecutive: bool = True,
) -> list[Segment]:
    """ASR 세그먼트에 화자를 붙이고 Segment 리스트로 변환한다."""
    labeled: list[Segment] = []
    for a in asr_segments:
        if not a.text.strip():
            continue
        labeled.append(
            Segment(speaker=assign_speaker(a, turns), start=a.start, end=a.end, text=a.text.strip())
        )

    if not merge_consecutive or not labeled:
        return labeled

    merged: list[Segment] = [labeled[0].model_copy()]
    for seg in labeled[1:]:
        prev = merged[-1]
        if seg.speaker == prev.speaker:
            prev.text = f"{prev.text} {seg.text}".strip()
            prev.end = seg.end
        else:
            merged.append(seg.model_copy())
    return merged
