"""회의록 문체 — 개조식(명사형 종결 · 마침표 없음).

어체 자체는 프롬프트가 만든다. 여기서는 **마침표 제거가 결정적으로 동작하는지**와
숫자·버전·날짜의 점을 건드리지 않는지를 본다(로컬 소형 LLM이 지시를 흘려도 최소한
구두점만은 보장돼야 한다).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from minutes.render import render_markdown
from minutes.schema import Minutes
from minutes.style import strip_sentence_periods as strip

ROOT = Path(__file__).resolve().parent.parent


# ---- 마침표 제거 -----------------------------------------------------------

def test_trailing_period_removed():
    assert strip("실증 구역을 부산시 전체로 확정함.") == "실증 구역을 부산시 전체로 확정함"
    assert strip("API 연동 완료.") == "API 연동 완료"
    assert strip("8월 초까지 준비 필요") == "8월 초까지 준비 필요"   # 원래 없으면 그대로


def test_sentences_are_split_into_lines():
    """그냥 지우면 두 문장이 붙어 읽기 어려워진다 — 개조식은 한 줄에 한 가지."""
    got = strip("결정이 내려짐. 실증 구역은 부산시 전체를 포함하여 작성함.")
    assert got == "결정이 내려짐\n실증 구역은 부산시 전체를 포함하여 작성함"


@pytest.mark.parametrize("text", [
    "예산 1.5억 원으로 확정함",          # 소수점
    "v3.1 기준으로 진행함",              # 버전
    "2026-08-20까지 제출함",             # 날짜
    "TTA·NIA 협업 진행 중",              # 가운뎃점
    "담당: 기현 수석 (전략계획실)",       # 괄호
])
def test_meaningful_dots_and_marks_survive(text):
    assert strip(text) == text


def test_can_be_disabled(monkeypatch):
    monkeypatch.setenv("MINUTES_STRIP_PERIODS", "0")
    assert strip("서술체로 쓰기로 했다.") == "서술체로 쓰기로 했다."


def test_empty_and_none_safe():
    assert strip("") == ""


# ---- 스키마 통합 -----------------------------------------------------------

def test_minutes_fields_are_normalized():
    m = Minutes.model_validate({
        "meeting_title": "AIOT 사업 착수 회의",
        "agenda": ["사업자료 작성 방향 논의함."],
        "discussion": [{"topic": "AIOT 사업자료 작성",
                        "summary": "기현 수석 협업으로 진행함. 8월 초까지 준비 필요."}],
        "decisions": [{"content": "실증 구역을 부산시 전체로 확정함.",
                       "rationale": "TTA 협업 일정 때문임."}],
        "action_items": [{"task": "사업자료 초안 작성함.", "owner": "기현 수석",
                          "due_date": "2026-08-05"}],
        "open_issues": ["예산 규모 미정임."],
        "risks": ["8월 초 기한이 촉박함."],
    })
    assert m.agenda[0] == "사업자료 작성 방향 논의함"
    assert m.discussion[0].summary == "기현 수석 협업으로 진행함\n8월 초까지 준비 필요"
    assert m.decisions[0].content == "실증 구역을 부산시 전체로 확정함"
    assert m.decisions[0].rationale == "TTA 협업 일정 때문임"
    assert m.action_items[0].task == "사업자료 초안 작성함"
    assert m.open_issues[0] == "예산 규모 미정임"
    assert m.risks[0] == "8월 초 기한이 촉박함"
    # 이름·날짜는 손대지 않는다
    assert m.action_items[0].owner == "기현 수석"
    assert m.action_items[0].due_date == "2026-08-05"


def test_transcript_text_is_not_touched():
    """전사 원문은 보정 대상이 아니다 — 사람이 말한 그대로여야 한다."""
    from minutes.schema import Segment

    s = Segment(speaker="SPEAKER_00", start=0, end=3, text="그렇게 하기로 했습니다.")
    assert s.text == "그렇게 하기로 했습니다."


def test_rendered_markdown_has_no_sentence_periods():
    m = Minutes.model_validate({
        "meeting_title": "정기 회의",
        "discussion": [{"topic": "일정", "summary": "8월 초까지 준비 필요."}],
        "decisions": [{"content": "부산시 전체로 확정함.", "rationale": "TTA 일정 때문임."}],
        "action_items": [{"task": "초안 작성함.", "owner": "홍길동"}],
        "risks": ["기한 촉박함."],
    })
    md = render_markdown(m)
    offenders = [ln for ln in md.splitlines() if ln.rstrip().endswith(".")]
    assert not offenders, offenders


# ---- 프롬프트 -------------------------------------------------------------

def test_prompts_instruct_gaejosik():
    integrate = (ROOT / "prompts" / "03_integrate_minutes.md").read_text(encoding="utf-8")
    assert "개조식" in integrate
    assert "마침표" in integrate
    for ending in ("~함", "~됨", "~필요"):
        assert ending in integrate
    # 서술형 금지를 명시했는지
    assert "서술형" in integrate

    chunk = (ROOT / "prompts" / "02_chunk_summary.md").read_text(encoding="utf-8")
    assert "개조식" in chunk and "마침표" in chunk


def test_schema_hint_example_is_gaejosik():
    """LLM은 스키마 예시를 문체 예시로도 읽는다 — 예시부터 개조식이어야 한다."""
    from minutes.schema import MINUTES_JSON_HINT

    assert "확정함" in MINUTES_JSON_HINT
    assert "다." not in MINUTES_JSON_HINT
