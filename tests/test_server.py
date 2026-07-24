"""minutes.server (HTTP) 엔드포인트 + HTTP 워크플로 유효성 테스트."""

from __future__ import annotations

import json
from pathlib import Path

from minutes import server

ROOT = Path(__file__).resolve().parent.parent
HTTP_WF = ROOT / "workflows" / "vexa_meeting_http.json"


def test_health():
    assert server.ep_health({})["ok"] is True


def test_ep_ingest_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    out = tmp_path / "data" / "out" / "secure" / "vexa_m1"  # 없는 중첩 경로
    res = server.ep_ingest(
        {"platform": "google_meet", "meetingId": "m1", "profile": "secure",
         "glossary": str(ROOT / "glossary.yaml"), "out": str(out)}
    )
    assert res["ok"] is True
    assert res["segments"] >= 1
    assert out.with_suffix(".minutes.md").exists()


def test_ep_bot_dispatch_mock(monkeypatch):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    res = server.ep_bot_dispatch({"platform": "google_meet", "meeting": "abc"})
    assert res["status"] == "requested"


def test_meeting_field_missing_raises():
    import pytest

    with pytest.raises(KeyError):
        server._meeting({"platform": "google_meet"})


def test_http_workflow_uses_http_not_execute_command():
    wf = json.loads(HTTP_WF.read_text(encoding="utf-8"))
    types = {n["type"] for n in wf["nodes"]}
    assert "n8n-nodes-base.httpRequest" in types
    assert "n8n-nodes-base.executeCommand" not in types  # 버전 무관 핵심
    names = {n["name"] for n in wf["nodes"]}
    for src, conn in wf["connections"].items():
        assert src in names
        for outs in conn["main"]:
            for link in outs:
                assert link["node"] in names
