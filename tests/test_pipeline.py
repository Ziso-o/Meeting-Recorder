"""Phase 3 테스트 — 결합 파이프라인 e2e + n8n 워크플로우 JSON 유효성."""

from __future__ import annotations

import json
from pathlib import Path

from minutes import pipeline

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "workflows" / "meeting_minutes.json"


def test_pipeline_end_to_end_mock(tmp_path, monkeypatch):
    """오디오(mock) → transcript + minutes(json/md)까지 한 번에 생성돼야 한다."""
    monkeypatch.setenv("ASR_ENGINE", "mock")
    monkeypatch.setenv("DIARIZER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    audio = tmp_path / "secure_meeting.m4a"
    audio.write_bytes(b"")  # mock 엔진은 내용 불필요

    rc = pipeline.main(
        ["--audio", str(audio), "--profile", "secure", "--glossary", str(ROOT / "glossary.yaml")]
    )
    assert rc == 0

    stem = tmp_path / "secure_meeting"
    transcript = stem.with_suffix(".transcript.json")
    minutes_json = stem.with_suffix(".minutes.json")
    minutes_md = stem.with_suffix(".minutes.md")
    assert transcript.exists() and minutes_json.exists() and minutes_md.exists()

    # transcript는 Phase 1 입력 스키마여야 한다
    doc = json.loads(transcript.read_text(encoding="utf-8"))
    assert "segments" in doc and doc["segments"]
    # minutes는 핵심 섹션 포함
    assert "## 결정 사항" in minutes_md.read_text(encoding="utf-8")


def test_workflow_json_is_valid_and_wired():
    wf = json.loads(WORKFLOW.read_text(encoding="utf-8"))

    names = {n["name"] for n in wf["nodes"]}
    # 핵심 노드 존재
    for expected in (
        "Config",
        "전사 (transcribe)",
        "회의록 생성 (generate)",
        "보안등급 분기",
        "배포: 보안(secure)",
        "배포: 내부(internal)",
        "에러 트리거",
    ):
        assert expected in names, f"누락 노드: {expected}"

    # 노드 id 유일성
    ids = [n["id"] for n in wf["nodes"]]
    assert len(ids) == len(set(ids))

    # 연결의 대상 노드는 모두 실제 노드여야 함
    for src, conn in wf["connections"].items():
        assert src in names
        for outputs in conn["main"]:
            for link in outputs:
                assert link["node"] in names

    # 보안등급 분기는 2개 출력(secure / internal)
    branch = wf["connections"]["보안등급 분기"]["main"]
    assert len(branch) == 2


def test_workflow_has_retry_on_execute_nodes():
    wf = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    exec_nodes = [n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.executeCommand"]
    assert exec_nodes
    assert all(n.get("retryOnFail") for n in exec_nodes)
