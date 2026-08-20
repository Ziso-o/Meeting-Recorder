"""회의록 스키마 (pydantic 검증).

decisions와 action_items 누락이 이 시스템의 최대 실패모드다.
스키마는 이 두 필드를 필수로 두되, "명시적 결정이 없으면 빈 배열"을 허용한다
(추측 금지 규칙은 프롬프트에서 강제).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from .style import strip_sentence_periods

#: 개조식 본문 필드 — 문장 끝 마침표를 자동으로 없앤다(어체는 프롬프트가 만든다).
#: 전사(Segment.text)에는 쓰지 않는다 — 원문은 그대로 보존해야 한다.
Brief = Annotated[str, AfterValidator(strip_sentence_periods)]


# ---- 입력(전사) 세그먼트 ----
class Segment(BaseModel):
    """화자 라벨이 붙은 전사 세그먼트 (Phase 2 출력 == Phase 1 입력)."""

    speaker: str
    start: float = Field(..., description="시작 시각(초)")
    end: float = Field(..., description="종료 시각(초)")
    text: str


# ---- 출력(회의록) 하위 구조 ----
class Discussion(BaseModel):
    topic: Brief
    summary: Brief


class Decision(BaseModel):
    content: Brief
    rationale: Brief = ""


class ActionItem(BaseModel):
    task: Brief
    owner: str = ""          # 사람 이름 — 손대지 않는다
    due_date: str = ""       # YYYY-MM-DD
    status: str = "open"


# ---- 최종 회의록 ----
class Minutes(BaseModel):
    """통합 회의록 스키마. LLM 통합 단계 출력이 반드시 이 형태여야 한다."""

    meeting_title: str
    date: str = ""
    attendees: list[str] = Field(default_factory=list)   # 이름 — 손대지 않는다
    agenda: list[Brief] = Field(default_factory=list)
    discussion: list[Discussion] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_issues: list[Brief] = Field(default_factory=list)
    risks: list[Brief] = Field(default_factory=list)


# JSON 스키마 문자열 — 프롬프트에 주입해 LLM 출력 형식을 강제할 때 사용.
MINUTES_JSON_HINT = """{
  "meeting_title": "회의 제목",
  "date": "YYYY-MM-DD",
  "attendees": ["참석자1", "참석자2"],
  "agenda": ["안건 (개조식·마침표 없음)"],
  "discussion": [{"topic": "논의 주제", "summary": "협업으로 진행함\\n8월 초까지 준비 필요"}],
  "decisions": [{"content": "실증 구역을 부산시 전체로 확정함", "rationale": "TTA 협업 일정 때문임"}],
  "action_items": [{"task": "사업자료 초안 작성", "owner": "담당자", "due_date": "YYYY-MM-DD", "status": "open"}],
  "open_issues": ["결론 없이 넘어간 사항 (개조식)"],
  "risks": ["8월 초 기한 촉박함"]
}"""
