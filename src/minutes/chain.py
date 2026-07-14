"""3단 LLM 체인: 용어교정 → 청크요약 → 통합 회의록.

정지조건은 관측 가능한 신호(pydantic 스키마 검증)로 둔다.
통합 단계에서 스키마 검증 실패 시 1회 재시도(오류 힌트를 덧붙여)한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .chunk import chunk_segments, render_segments
from .glossary import glossary_to_prompt
from .providers.base import LLMProvider
from .schema import MINUTES_JSON_HINT, Minutes, Segment

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


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
def correct_terms(
    segments: list[Segment], glossary_text: str, provider: LLMProvider
) -> list[Segment]:
    seg_json = json.dumps(
        [{"speaker": s.speaker, "text": s.text} for s in segments],
        ensure_ascii=False,
    )
    prompt = _fill(
        _load_prompt("01_term_correction.md"),
        GLOSSARY=glossary_text,
        SEGMENTS_JSON=seg_json,
    )
    try:
        corrected = _extract_json(provider.generate(prompt))
        if isinstance(corrected, list) and len(corrected) == len(segments):
            return [
                seg.model_copy(update={"text": str(new_text)})
                for seg, new_text in zip(segments, corrected)
            ]
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    # 실패는 치명적이지 않다 — 원문 유지(복구 가능 오류).
    return segments


# ---- 단계 2: 청크 요약 ----
def summarize_chunks(
    segments: list[Segment], glossary_text: str, provider: LLMProvider
) -> list[str]:
    template = _load_prompt("02_chunk_summary.md")
    summaries: list[str] = []
    for chunk in chunk_segments(segments):
        prompt = _fill(
            template,
            GLOSSARY=glossary_text,
            CHUNK_TEXT=render_segments(chunk),
        )
        summaries.append(provider.generate(prompt).strip())
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
) -> Minutes:
    glossary_text = glossary_to_prompt(glossary or {})
    meta = meta or {}

    corrected = correct_terms(segments, glossary_text, provider)
    summaries = summarize_chunks(corrected, glossary_text, provider)
    minutes = integrate(summaries, meta, glossary_text, provider)

    # 메타데이터로 비어있는 상위 필드 보완(LLM이 놓친 경우).
    if not minutes.meeting_title and meta.get("meeting_title"):
        minutes.meeting_title = str(meta["meeting_title"])
    if not minutes.date and meta.get("date"):
        minutes.date = str(meta["date"])
    return minutes
