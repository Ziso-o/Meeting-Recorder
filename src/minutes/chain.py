"""3단 LLM 체인: 용어교정 → 청크요약 → 통합 회의록.

정지조건은 관측 가능한 신호(pydantic 스키마 검증)로 둔다.
통합 단계에서 스키마 검증 실패 시 1회 재시도(오류 힌트를 덧붙여)한다.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .chunk import chunk_segments, render_segments
from .glossary import glossary_to_prompt
from .providers.base import LLMProvider
from .schema import MINUTES_JSON_HINT, Minutes, Segment

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

#: on_progress(stage, done, total) — stage: terms | summary | integrate
Progress = Callable[[str, int, int], None]


def _noop(stage: str, done: int, total: int) -> None:
    return None


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _fill(template: str, **vars: str) -> str:
    """{{KEY}} 토큰을 치환한다(JSON 중괄호와 충돌 없는 방식)."""
    out = template
    for key, val in vars.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def _extract_json(text: str) -> Any:
    """LLM 응답에서 JSON을 관대하게 추출(코드펜스/잡텍스트 허용)."""
    text = text.strip()
    if text.startswith("```"):
        # ```json ... ``` 펜스 제거
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 첫 번째 { ... } 또는 [ ... ] 블록만 잘라 재시도
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
    raise json.JSONDecodeError("JSON을 찾을 수 없음", text, 0)


# ---- 단계 1: 용어 교정 ----
def term_correction_enabled() -> bool:
    """LLM_TERM_CORRECTION=0 이면 건너뛴다.

    이 단계는 LLM에게 전사 전문을 **그대로 다시 출력**하게 하므로 가장 비싸다
    (출력 길이 ≈ 입력 길이). CPU 로컬 LLM에서는 이 한 단계가 전체 시간을 배로 늘린다.
    용어 교정 없이도 회의록은 나오므로 끌 수 있게 둔다.
    """
    return os.environ.get("LLM_TERM_CORRECTION", "1").lower() not in ("0", "false", "off", "no")


def _correct_chunk(
    chunk: list[Segment], glossary_text: str, provider: LLMProvider
) -> list[Segment]:
    """청크 하나를 교정. 실패하면 원문 그대로 — 여기서 예외를 올리지 않는다."""
    prompt = _fill(
        _load_prompt("01_term_correction.md"),
        GLOSSARY=glossary_text,
        SEGMENTS_JSON=json.dumps(
            [{"speaker": s.speaker, "text": s.text} for s in chunk], ensure_ascii=False
        ),
    )
    try:
        corrected = _extract_json(provider.generate(prompt))
        if isinstance(corrected, list) and len(corrected) == len(chunk):
            return [
                seg.model_copy(update={"text": str(new_text)})
                for seg, new_text in zip(chunk, corrected)
            ]
    except Exception as e:  # noqa: BLE001  타임아웃·연결오류 포함 — 비치명 단계다
        print(f"  용어 교정 건너뜀(원문 유지): {type(e).__name__}: {e}")
    return chunk


def correct_terms(
    segments: list[Segment],
    glossary_text: str,
    provider: LLMProvider,
    on_progress: Progress = _noop,
) -> list[Segment]:
    """용어 교정 — **청크 단위**로 나눠 호출한다.

    전사 전체를 한 프롬프트에 넣으면 긴 회의에서 반드시 타임아웃이 난다.
    """
    if not term_correction_enabled():
        on_progress("terms", 1, 1)
        return segments

    chunks = chunk_segments(segments)
    out: list[Segment] = []
    for i, chunk in enumerate(chunks, 1):
        out.extend(_correct_chunk(chunk, glossary_text, provider))
        on_progress("terms", i, len(chunks))
    return out


# ---- 단계 2: 청크 요약 ----
def summarize_chunks(
    segments: list[Segment],
    glossary_text: str,
    provider: LLMProvider,
    on_progress: Progress = _noop,
) -> list[str]:
    template = _load_prompt("02_chunk_summary.md")
    chunks = chunk_segments(segments)
    summaries: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        prompt = _fill(
            template,
            GLOSSARY=glossary_text,
            CHUNK_TEXT=render_segments(chunk),
        )
        summaries.append(provider.generate(prompt).strip())
        on_progress("summary", i, len(chunks))
    return summaries


# ---- 단계 3: 통합 (검증 + 1회 재시도) ----
def integrate(
    summaries: list[str],
    meta: dict[str, Any],
    glossary_text: str,
    provider: LLMProvider,
) -> Minutes:
    template = _load_prompt("03_integrate_minutes.md")
    meta_text = "\n".join(f"- {k}: {v}" for k, v in meta.items() if v) or "(제공된 정보 없음)"
    summaries_text = "\n\n".join(f"### 구간 {i + 1}\n{s}" for i, s in enumerate(summaries))

    base_prompt = _fill(
        template,
        GLOSSARY=glossary_text,
        META=meta_text,
        CHUNK_SUMMARIES=summaries_text,
        SCHEMA=MINUTES_JSON_HINT,
    )

    last_err = ""
    for attempt in range(2):  # 최초 + 1회 재시도
        prompt = base_prompt
        if attempt == 1:
            prompt += (
                f"\n\n## 재시도 안내\n직전 출력이 스키마 검증에 실패했다: {last_err}\n"
                "설명 없이 스키마와 정확히 일치하는 순수 JSON만 다시 출력하라."
            )
        raw = provider.generate(prompt)
        try:
            data = _extract_json(raw)
            return Minutes.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = str(e)[:300]

    raise ValueError(f"통합 단계 스키마 검증 2회 실패: {last_err}")


# ---- 전체 파이프라인 ----
def generate_minutes(
    segments: list[Segment],
    provider: LLMProvider,
    glossary: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    on_progress: Progress = _noop,
) -> Minutes:
    glossary_text = glossary_to_prompt(glossary or {})
    meta = meta or {}

    corrected = correct_terms(segments, glossary_text, provider, on_progress)
    summaries = summarize_chunks(corrected, glossary_text, provider, on_progress)
    on_progress("integrate", 0, 1)
    minutes = integrate(summaries, meta, glossary_text, provider)
    on_progress("integrate", 1, 1)

    # 메타데이터로 비어있는 상위 필드 보완(LLM이 놓친 경우).
    if not minutes.meeting_title and meta.get("meeting_title"):
        minutes.meeting_title = str(meta["meeting_title"])
    if not minutes.date and meta.get("date"):
        minutes.date = str(meta["date"])
    return minutes
