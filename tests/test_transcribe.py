"""Phase 2 테스트 — 병합 로직 + mock e2e (GPU/네트워크/오디오 없이)."""

from __future__ import annotations

from minutes.asr import merge_segments, select_asr_engine, select_diarizer
from minutes.asr.base import ASRSegment, SpeakerTurn
from minutes.asr.merge import assign_speaker
from minutes.glossary import glossary_terms
from minutes.schema import Segment


def test_assign_speaker_by_overlap():
    turns = [
        SpeakerTurn(speaker="A", start=0.0, end=5.0),
        SpeakerTurn(speaker="B", start=5.0, end=10.0),
    ]
    seg = ASRSegment(start=6.0, end=9.0, text="x")
    assert assign_speaker(seg, turns) == "B"


def test_assign_speaker_no_overlap_uses_nearest():
    turns = [SpeakerTurn(speaker="A", start=0.0, end=2.0)]
    seg = ASRSegment(start=10.0, end=11.0, text="x")
    assert assign_speaker(seg, turns) == "A"


def test_merge_consecutive_same_speaker():
    asr = [
        ASRSegment(start=0.0, end=3.0, text="첫째"),
        ASRSegment(start=3.0, end=6.0, text="둘째"),
        ASRSegment(start=6.0, end=9.0, text="셋째"),
    ]
    turns = [
        SpeakerTurn(speaker="A", start=0.0, end=6.0),
        SpeakerTurn(speaker="B", start=6.0, end=9.0),
    ]
    merged = merge_segments(asr, turns)
    assert [m.speaker for m in merged] == ["A", "B"]
    assert merged[0].text == "첫째 둘째"
    assert merged[0].end == 6.0
    assert merged[1].text == "셋째"


def test_merge_drops_empty_text():
    asr = [ASRSegment(start=0.0, end=1.0, text="  "), ASRSegment(start=1.0, end=2.0, text="내용")]
    merged = merge_segments(asr, [])
    assert len(merged) == 1
    assert merged[0].text == "내용"


def test_mock_pipeline_produces_phase1_schema(monkeypatch):
    """mock 엔진 e2e — 출력이 Phase 1 입력 스키마(Segment)와 호환돼야 한다."""
    monkeypatch.setenv("ASR_ENGINE", "mock")
    monkeypatch.setenv("DIARIZER", "mock")
    engine = select_asr_engine()
    diarizer = select_diarizer()
    asr = engine.transcribe("dummy.wav", initial_prompt="")
    turns = diarizer.diarize("dummy.wav")
    segments = merge_segments(asr, turns)

    assert segments and all(isinstance(s, Segment) for s in segments)
    # Phase 1 스키마로 재검증 가능해야 함
    for s in segments:
        Segment.model_validate(s.model_dump())
    assert {s.speaker for s in segments} <= {"SPEAKER_00", "SPEAKER_01"}


def test_diarizer_off_returns_single_speaker(monkeypatch):
    monkeypatch.setenv("ASR_ENGINE", "mock")
    monkeypatch.setenv("DIARIZER", "off")
    assert select_diarizer() is None
    engine = select_asr_engine()
    segments = merge_segments(engine.transcribe("d.wav"), [])
    assert {s.speaker for s in segments} == {"SPEAKER_00"}


def test_glossary_terms_for_initial_prompt():
    g = {
        "projects": ["지능형 통합관제 플랫폼 구축 사업"],
        "organizations": ["행정안전부"],
        "acronyms": [{"term": "RAG", "aliases": ["래그"]}, "API"],
        "people": ["이팀장"],
    }
    terms = glossary_terms(g)
    assert "RAG" in terms and "행정안전부" in terms and "이팀장" in terms
    assert "래그" not in terms  # 정답만, 오인식 별칭은 제외
