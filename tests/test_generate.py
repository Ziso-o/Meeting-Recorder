"""Phase 1 end-to-end 테스트 (MockProvider — 네트워크 없이).

정지조건(관측 가능한 신호): 아래 테스트가 모두 통과해야 Phase 1 완료로 본다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from minutes.chain import generate_minutes
from minutes.glossary import glossary_to_prompt, load_glossary
from minutes.providers import MockProvider
from minutes.render import render_markdown
from minutes.schema import Minutes, Segment

FIXTURE = Path(__file__).parent / "fixtures" / "sample_transcript.json"
ROOT = Path(__file__).resolve().parent.parent


def _load_fixture() -> tuple[list[Segment], dict]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    segments = [Segment.model_validate(s) for s in data["segments"]]
    return segments, data["meta"]


def test_end_to_end_produces_valid_minutes():
    segments, meta = _load_fixture()
    glossary = load_glossary(ROOT / "glossary.yaml")
    provider = MockProvider()

    minutes = generate_minutes(segments, provider, glossary=glossary, meta=meta)

    assert isinstance(minutes, Minutes)
    assert minutes.meeting_title
    # 3단 체인이 모두 호출됐는지(관찰): 교정 1 + 청크요약 N + 통합 1
    assert provider.calls[0] == "term_correction"
    assert "chunk_summary" in provider.calls
    assert provider.calls[-1] == "integrate"


def test_markdown_renders_key_sections():
    segments, meta = _load_fixture()
    minutes = generate_minutes(segments, MockProvider(), meta=meta)
    md = render_markdown(minutes)
    assert "## 결정 사항" in md
    assert "## 액션 아이템" in md


def test_integrate_retries_once_on_invalid_json():
    """통합 단계가 처음엔 깨진 JSON, 재시도에서 유효 JSON을 받아 성공해야 한다."""
    segments, meta = _load_fixture()
    provider = MockProvider(fail_integrate_once=True)
    minutes = generate_minutes(segments, provider, meta=meta)
    assert isinstance(minutes, Minutes)
    assert provider.calls.count("integrate") == 2  # 최초 실패 + 재시도


def test_missing_decisions_allowed_empty():
    """결정/액션이 없어도(빈 배열) 스키마·렌더링이 깨지지 않아야 한다."""
    m = Minutes(meeting_title="빈 회의")
    assert m.decisions == []
    assert m.action_items == []
    md = render_markdown(m)
    assert "명시적 결정 없음" in md
    assert "지정된 액션 아이템 없음" in md


def test_term_correction_preserves_segment_count():
    segments, _ = _load_fixture()
    from minutes.chain import correct_terms

    glossary_text = glossary_to_prompt(load_glossary(ROOT / "glossary.yaml"))
    corrected = correct_terms(segments, glossary_text, MockProvider())
    assert len(corrected) == len(segments)
    assert all(isinstance(s, Segment) for s in corrected)


def test_provider_selection_by_profile(monkeypatch):
    """secure→ollama, internal→gemini(키 있을 때) 로 프로바이더가 선택돼야 한다."""
    from minutes.config import provider_for_profile

    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    assert provider_for_profile("secure").name == "ollama"
    assert provider_for_profile("internal").name == "gemini"
    with pytest.raises(ValueError):
        provider_for_profile("unknown")


def test_internal_falls_back_to_ollama_without_key(monkeypatch):
    """무료·로컬 정책: internal이라도 GEMINI_API_KEY가 없으면 로컬 Ollama로 폴백."""
    from minutes.config import provider_for_profile

    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert provider_for_profile("internal").name == "ollama"
    assert provider_for_profile("secure").name == "ollama"


def test_explicit_llm_provider_overrides(monkeypatch):
    """LLM_PROVIDER를 명시하면 프로파일 기본을 덮어쓴다."""
    from minutes.config import provider_for_profile

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    assert provider_for_profile("internal").name == "mock"
    assert provider_for_profile("secure").name == "mock"
