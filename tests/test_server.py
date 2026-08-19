"""minutes.server (HTTP) 엔드포인트 + HTTP 워크플로 유효성 테스트."""

from __future__ import annotations

import json
from pathlib import Path

from minutes import server

ROOT = Path(__file__).resolve().parent.parent
HTTP_WF = ROOT / "workflows" / "vexa_meeting_http.json"


def test_health():
    assert server.ep_health({})["ok"] is True


def test_health_reports_mock_mode(monkeypatch):
    monkeypatch.delenv("VEXA_CLIENT", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert server.ep_health({})["mock"]["any"] is False
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    m = server.ep_health({})["mock"]
    assert m["vexa"] is True and m["any"] is True


def test_dashboard_has_mock_badge():
    assert "modeBadge" in server.INDEX_HTML and "흉내 모드" in server.INDEX_HTML


def test_dashboard_has_mode_switch():
    assert "mockSw" in server.INDEX_HTML and "/mode" in server.INDEX_HTML


def test_ep_mode_toggle_restores_baseline(monkeypatch):
    monkeypatch.delenv("VEXA_CLIENT", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ASR_ENGINE", "faster-whisper")  # 실제 값은 보존돼야
    server._baseline = None
    server._capture_baseline()

    assert server.ep_mode({"mock": True})["mock"]["any"] is True
    import os

    assert os.environ["VEXA_CLIENT"] == "mock"

    res = server.ep_mode({"mock": False})
    assert res["mock"]["any"] is False
    assert "VEXA_CLIENT" not in os.environ          # mock 값은 제거
    assert os.environ["ASR_ENGINE"] == "faster-whisper"  # 실제 값은 복원
    server._baseline = None


def test_ep_mode_requires_flag():
    import pytest

    with pytest.raises(KeyError):
        server.ep_mode({})


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


def test_resolve_target_url_and_fields():
    # 링크면 플랫폼 자동 인식(zoom), 명시 platform이면 그대로
    assert server._resolve_target(
        {"url": "https://us05web.zoom.us/j/85130931937?pwd=x"}
    ) == ("zoom", "85130931937")
    assert server._resolve_target({"platform": "teams", "meeting": "19:abc"}) == ("teams", "19:abc")


def test_infer_platform_from_bare_id():
    # 링크·platform 없이 ID만 → 형태로 추정
    assert server._resolve_target({"meeting": "abc-defg-hij"}) == ("google_meet", "abc-defg-hij")
    assert server._resolve_target({"meeting": "85130931937"}) == ("zoom", "85130931937")


def test_ep_ingest_by_url_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    out = tmp_path / "z"
    res = server.ep_ingest(
        {"url": "https://us05web.zoom.us/j/85130931937", "profile": "secure",
         "glossary": str(ROOT / "glossary.yaml"), "out": str(out)}
    )
    assert res["ok"] is True and res["segments"] >= 1


def test_meeting_field_missing_raises():
    import pytest

    with pytest.raises(KeyError):
        server._meeting({"platform": "google_meet"})


def test_ep_status_mock(monkeypatch):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    res = server.ep_status({})
    assert res["ok"] is True and "vexa" in res


def test_ep_files_and_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MINUTES_HOME", str(tmp_path))
    d = tmp_path / "data" / "out" / "secure"
    d.mkdir(parents=True)
    (d / "vexa_m1.minutes.md").write_text("# 회의록\n결정1", encoding="utf-8")
    (d / "vexa_m1.transcript.json").write_text('{"segments":[]}', encoding="utf-8")
    (d / "vexa_m1.minutes.json").write_text("{}", encoding="utf-8")  # 목록에서 제외돼야

    files = server.ep_files({})["files"]
    kinds = sorted(f["kind"] for f in files)
    assert kinds == ["minutes", "transcript"]  # minutes.json 은 제외

    md = next(f for f in files if f["kind"] == "minutes")
    got = server.ep_file({"path": md["path"]})
    assert "회의록" in got["content"]


def test_upload_delete_rename(tmp_path, monkeypatch):
    monkeypatch.setenv("MINUTES_HOME", str(tmp_path))
    (tmp_path / "data").mkdir()
    # 업로드 → 목록에 등장
    up = server.ep_upload({"kind": "minutes", "name": "우리 회의.md", "content": "# 제목\n결정1"})
    assert up["ok"] and up["path"].endswith(".minutes.md")
    files = server.ep_files({})["files"]
    assert any(f["path"] == up["path"] for f in files)
    # 이름 변경(확장자 유지)
    ren = server.ep_rename({"path": up["path"], "name": "새이름"})
    assert ren["path"].endswith("새이름.minutes.md")
    # 삭제
    assert server.ep_delete({"path": ren["path"]})["ok"] is True
    assert server.ep_files({})["files"] == []


def test_delete_traversal_and_type_blocked(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setenv("MINUTES_HOME", str(tmp_path))
    (tmp_path / "data").mkdir()
    with pytest.raises(ValueError):
        server.ep_delete({"path": "../../etc/passwd"})
    # 관리 대상 아닌 확장자는 삭제 거부
    (tmp_path / "data" / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        server.ep_delete({"path": "keep.txt"})
    assert (tmp_path / "data" / "keep.txt").exists()


def test_dashboard_has_upload_controls():
    assert "doUpload" in server.INDEX_HTML and "renFile" in server.INDEX_HTML


def test_ep_file_path_traversal_blocked(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setenv("MINUTES_HOME", str(tmp_path))
    (tmp_path / "data").mkdir()
    with pytest.raises(ValueError):
        server.ep_file({"path": "../../etc/passwd"})


def test_dispatch_registers_tracking(monkeypatch):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    server._TRACKED.clear()
    server.ep_bot_dispatch({"url": "https://meet.google.com/abc-defg-hij", "profile": "secure"})
    tr = server.ep_tracked({})["tracked"]
    assert any(t["meeting"] == "abc-defg-hij" and t["status"] == "waiting" for t in tr)
    server._TRACKED.clear()


def test_dispatch_auto_false_no_tracking(monkeypatch):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    server._TRACKED.clear()
    server.ep_bot_dispatch({"platform": "google_meet", "meeting": "no-track", "auto": False})
    assert server.ep_tracked({})["tracked"] == []


def test_watch_generates_after_meeting_ends(tmp_path, monkeypatch):
    # 참석(live)했다가 봇이 사라지면 → 자동 회의록 생성(done)
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("MINUTES_HOME", str(tmp_path))
    monkeypatch.chdir(ROOT)  # glossary.yaml 상대경로
    server._TRACKED.clear()
    key = ("google_meet", "m-auto")
    server._track(*key, "secure", "자동테스트")

    # 1) 봇이 실행 중으로 보이게 → live/seen
    monkeypatch.setattr(server, "_running_keys", lambda s: {key})
    server._watch_once()
    assert server._TRACKED[key]["status"] == "live"

    # 2) 봇이 사라짐 → 생성 완료
    monkeypatch.setattr(server, "_running_keys", lambda s: set())
    server._watch_once()
    assert server._TRACKED[key]["status"] == "done"
    assert server._TRACKED[key]["stem"]
    server._TRACKED.clear()


def test_dashboard_has_nav():
    for label in ("회의 참석", "상태 모니터링", "녹취파일", "회의록"):
        assert label in server.INDEX_HTML


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
