"""Phase 4 테스트 — Vexa 변환 + mock 클라이언트 + bot ingest e2e + 워크플로우 유효성."""

from __future__ import annotations

import json
from pathlib import Path

from minutes import bot
from minutes.schema import Segment
from minutes.vexa import select_vexa_client, vexa_to_segments
from minutes.vexa.mock import MockVexaClient

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "workflows" / "vexa_meeting.json"


def test_vexa_to_segments_maps_schema():
    payload = {
        "segments": [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.0, "text": "안녕하세요"},
            {"speaker": "SPEAKER_01", "start": 2.0, "end": 4.0, "text": "  "},  # 빈 텍스트 제거
            {"speaker": "SPEAKER_01", "start": 4.0, "end": 6.0, "text": "네"},
        ]
    }
    segs = vexa_to_segments(payload)
    assert len(segs) == 2
    assert all(isinstance(s, Segment) for s in segs)
    assert segs[0].speaker == "SPEAKER_00"


def test_vexa_to_segments_defensive_fields():
    # 대체 필드명(start_time/end_time)도 파싱
    payload = {"data": {"segments": [{"speaker_id": "S1", "start_time": "1.5", "end_time": "3", "text": "x"}]}}
    segs = vexa_to_segments(payload)
    assert len(segs) == 1
    assert segs[0].start == 1.5 and segs[0].end == 3.0


def test_select_vexa_client_mock(monkeypatch):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    monkeypatch.setenv("VEXA_BOT_NAME", "테스트봇")
    client = select_vexa_client()
    assert isinstance(client, MockVexaClient)
    assert client.bot_name == "테스트봇"
    res = client.request_bot("google_meet", "abc-def")
    assert res["status"] == "requested"
    assert client.dispatched == [("google_meet", "abc-def")]


def test_bot_ingest_end_to_end(tmp_path, monkeypatch):
    """Vexa 전사(mock) → 회의록 생성까지 CLI로 e2e."""
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    stem = tmp_path / "vexa_mtg"

    rc = bot.main(
        [
            "ingest",
            "--platform", "google_meet",
            "--meeting", "abc-defg-hij",
            "--profile", "secure",
            "--glossary", str(ROOT / "glossary.yaml"),
            "--out", str(stem),
        ]
    )
    assert rc == 0
    assert stem.with_suffix(".transcript.json").exists()
    assert stem.with_suffix(".minutes.json").exists()
    md = stem.with_suffix(".minutes.md").read_text(encoding="utf-8")
    assert "## 결정 사항" in md


def test_bot_request_and_stop(monkeypatch, capsys):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    assert bot.main(["request", "--platform", "google_meet", "--meeting", "m1"]) == 0
    assert bot.main(["stop", "--meeting", "m1"]) == 0


def test_bot_ingest_creates_nested_out_dir(tmp_path, monkeypatch):
    """--out이 없는 하위 폴더(data/out/secure/...)를 가리켜도 CLI가 폴더를 만들어야 한다."""
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    stem = tmp_path / "data" / "out" / "secure" / "vexa_m1"  # 존재하지 않는 중첩 경로
    rc = bot.main(
        [
            "ingest", "--platform", "google_meet", "--meeting", "m1",
            "--profile", "secure", "--glossary", str(ROOT / "glossary.yaml"),
            "--out", str(stem),
        ]
    )
    assert rc == 0
    assert stem.with_suffix(".minutes.md").exists()


def test_vexa_local_workflow_portable():
    """네이티브 워크플로: 유효 + 배선 + 셸 cp/mkdir -p 미사용(포터블) 확인."""
    wf = json.loads((ROOT / "workflows" / "vexa_meeting_local.json").read_text(encoding="utf-8"))
    names = {n["name"] for n in wf["nodes"]}
    for expected in ("웹훅: 봇 참석 요청", "봇 dispatch", "Config Vexa", "인제스트 (Vexa전사→회의록)"):
        assert expected in names
    # 연결 대상 유효
    for src, conn in wf["connections"].items():
        assert src in names
        for outs in conn["main"]:
            for link in outs:
                assert link["node"] in names
    # 포터블: executeCommand 명령에 POSIX 전용 셸 구문이 없어야 함
    cmds = " ".join(
        n["parameters"].get("command", "")
        for n in wf["nodes"]
        if n["type"] == "n8n-nodes-base.executeCommand"
    )
    assert "mkdir -p" not in cmds
    assert "cp " not in cmds
    assert "cd " not in cmds


def test_vexa_workflow_json_valid_and_wired():
    wf = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    names = {n["name"] for n in wf["nodes"]}
    for expected in (
        "웹훅: 봇 참석 요청",
        "봇 dispatch",
        "웹훅: 회의 종료",
        "Config Vexa",
        "인제스트 (Vexa전사→회의록)",
        "보안등급 분기",
        "에러 트리거",
    ):
        assert expected in names, f"누락 노드: {expected}"

    ids = [n["id"] for n in wf["nodes"]]
    assert len(ids) == len(set(ids))

    for src, conn in wf["connections"].items():
        assert src in names
        for outputs in conn["main"]:
            for link in outputs:
                assert link["node"] in names

    # 보안등급 분기 2출력
    assert len(wf["connections"]["보안등급 분기"]["main"]) == 2
