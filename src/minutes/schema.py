"""회의록 스키마 (pydantic 검증).

decisions와 action_items 누락이 이 시스템의 최대 실패모드다.
스키마는 이 두 필드를 필수로 두되, "명시적 결정이 없으면 빈 배열"을 허용한다
(추측 금지 규칙은 프롬프트에서 강제).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---- 입력(전사) 세그먼트 ----
class Segment(BaseModel):
    """화자 라벨이 붙은 전사 세그먼트 (Phase 2 출력 == Phase 1 입력)."""

    speaker: str
    start: float = Field(..., description="시작 시각(초)")
    end: float = Field(..., description="종료 시각(초)")
    text: str


# ---- 출력(회의록) 하위 구조 ----
class Discussion(BaseModel):
    topic: str
    summary: str


class Decision(BaseModel):
    content: str
    rationale: str = ""


class ActionItem(BaseModel):
    task: str
    owner: str = ""
    due_date: str = ""
    status: str = "open"


# ---- 최종 회의록 ----
class Minutes(BaseModel):
    """통합 회의록 스키마. LLM 통합 단계 출력이 반드시 이 형태여야 한다."""

    meeting_title: str
    date: str = ""
    attendees: list[str] = Field(default_factory=list)
    agenda: list[str] = Field(default_factory=list)
    discussion: list[Discussion] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


# JSON 스키마 문자열 — 프롬프트에 주입해 LLM 출력 형식을 강제할 때 사용.
MINUTES_JSON_HINT = """{
  "meeting_title": "회의 제목",
  "date": "YYYY-MM-DD",
  "attendees": ["참석자1", "참석자2"],
  "agenda": ["안건1", "안건2"],
  "discussion": [{"topic": "논의 주제", "summary": "논의 요약"}],
  "decisions": [{"content": "결정 사항", "rationale": "결정 근거"}],
  "action_items": [{"task": "할 일", "owner": "담당자", "due_date": "YYYY-MM-DD", "status": "open"}],
  "open_issues": ["미결 사항"],
  "risks": ["리스크"]
}"""
