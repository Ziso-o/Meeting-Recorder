"""회의 링크 파서 + 링크로 봇 dispatch 테스트."""

from __future__ import annotations

import pytest

from minutes import server
from minutes.vexa import parse_meeting_url


def test_google_meet_url():
    r = parse_meeting_url("https://meet.google.com/abc-defg-hij")
    assert r == {"platform": "google_meet", "native_meeting_id": "abc-defg-hij"}


def test_google_meet_bare_code():
    r = parse_meeting_url("abc-defg-hij")
    assert r["platform"] == "google_meet" and r["native_meeting_id"] == "abc-defg-hij"


def test_zoom_url_with_passcode():
    r = parse_meeting_url("https://us05web.zoom.us/j/12345678901?pwd=SeCret")
    assert r["platform"] == "zoom"
    assert r["native_meeting_id"] == "12345678901"
    assert r["passcode"] == "SeCret"


def test_jitsi_url():
    r = parse_meeting_url("https://meet.jit.si/MyRoomName")
    assert r == {"platform": "jitsi", "native_meeting_id": "MyRoomName"}


def test_teams_best_effort():
    r = parse_meeting_url("https://teams.microsoft.com/l/meetup-join/19%3ameeting_xxx")
    assert r["platform"] == "teams"


def test_teams_live_extracts_id():
    r = parse_meeting_url("https://teams.live.com/meet/937518080098?p=Be3vcnvLc4bNyf06Cz")
    assert r["platform"] == "teams"
    assert r["native_meeting_id"] == "937518080098"


def test_server_has_web_ui():
    assert "봇 참석" in server.INDEX_HTML and "/bot/dispatch" in server.INDEX_HTML


def test_unknown_url_raises():
    with pytest.raises(ValueError):
        parse_meeting_url("https://example.com/whatever")


def test_dispatch_by_url_mock(monkeypatch):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    res = server.ep_bot_dispatch({"url": "https://meet.google.com/abc-defg-hij"})
    assert res["status"] == "requested"
    assert res["platform"] == "google_meet"
    assert res["native_meeting_id"] == "abc-defg-hij"


def test_dispatch_zoom_forwards_meeting_url(monkeypatch):
    """zoom/jitsi는 전체 링크(meeting_url)를 그대로 넘겨야 한다(패스워드 포함)."""
    captured: dict = {}

    class Fake:
        bot_name = "회의록봇"

        def request_bot(self, platform, native_meeting_id, language="ko",
                        passcode="", meeting_url="", bot_name=""):
            captured.update(platform=platform, meeting=native_meeting_id,
                            passcode=passcode, meeting_url=meeting_url)
            return {"status": "requested", "platform": platform,
                    "native_meeting_id": native_meeting_id}

    monkeypatch.setattr(server, "select_vexa_client", lambda: Fake())
    url = "https://us05web.zoom.us/j/86332083798?pwd=SeCret.1"
    res = server.ep_bot_dispatch({"url": url})
    assert res["status"] == "requested"
    assert captured["platform"] == "zoom"
    assert captured["meeting_url"] == url          # 전체 링크 전달
    assert captured["passcode"] == "SeCret.1"      # 링크의 pwd 파싱