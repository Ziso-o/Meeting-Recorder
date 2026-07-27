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


def test_unknown_url_raises():
    with pytest.raises(ValueError):
        parse_meeting_url("https://example.com/whatever")


def test_dispatch_by_url_mock(monkeypatch):
    monkeypatch.setenv("VEXA_CLIENT", "mock")
    res = server.ep_bot_dispatch({"url": "https://meet.google.com/abc-defg-hij"})
    assert res["status"] == "requested"
    assert res["platform"] == "google_meet"
    assert res["native_meeting_id"] == "abc-defg-hij"