"""HTTP 레벨 검증 — 녹음본 raw 바이너리 업로드 경로(핸들러/헤더/거부 응답).

`test_audio_upload.py` 가 함수 단위를 보고, 여기서는 실제 소켓으로 오가는
요청/응답(한글 파일명 헤더, 크기 거부 시 응답 도달성)을 본다.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.parse
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from minutes import server

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def live(tmp_path, monkeypatch):
    monkeypatch.setenv("MINUTES_HOME", str(tmp_path))
    monkeypatch.setenv("ASR_ENGINE", "mock")
    monkeypatch.setenv("DIARIZER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("MINUTES_MAX_UPLOAD_MB", "2")
    monkeypatch.chdir(ROOT)  # glossary.yaml 상대경로
    server._JOBS.clear()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    httpd.RequestHandlerClass.log_message = lambda *a, **k: None  # 테스트 출력 조용히
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1], tmp_path
    httpd.shutdown()
    httpd.server_close()
    server._JOBS.clear()


def _post_audio(port: int, name: str, data: bytes, query: str = "") -> tuple[int, dict]:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        c.request(
            "POST", "/api/upload/audio?" + (query or "profile=secure&auto=1"), body=data,
            headers={"X-Filename": urllib.parse.quote(name),
                     "Content-Type": "application/octet-stream",
                     "Content-Length": str(len(data))},
        )
        r = c.getresponse()
        return r.status, json.loads(r.read())
    finally:
        c.close()


def _get(port: int, path: str) -> tuple[int, dict]:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        c.request("GET", path)
        r = c.getresponse()
        return r.status, json.loads(r.read())
    finally:
        c.close()


def test_upload_korean_filename_then_minutes(live):
    port, home = live
    status, res = _post_audio(port, "클로바 노트 녹음.m4a", b"\x00\x01fake" * 20_000)
    assert status == 200 and res["ok"] is True
    assert res["name"] == "클로바 노트 녹음.m4a"  # URL 인코딩된 헤더가 원래대로 복원

    deadline = time.time() + 20
    while time.time() < deadline:
        job = _get(port, "/api/jobs")[1]["jobs"][0]
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert job["status"] == "done", job.get("error")

    kinds = {f["kind"] for f in _get(port, "/api/files")[1]["files"]}
    assert kinds == {"audio", "transcript", "minutes"}
    assert (home / "data" / "out" / "secure" / "클로바 노트 녹음.minutes.md").exists()


def test_oversize_gets_readable_error_not_broken_pipe(live):
    """상한을 넘겨도 클라이언트가 사유를 읽을 수 있어야 한다(남은 본문 버리기)."""
    port, _ = live
    status, res = _post_audio(port, "조금큰파일.m4a", b"z" * (3 * 1024 * 1024))
    assert status == 400 and "너무 큽니다" in res["error"]


def test_expect_100_rejects_before_body(live):
    """Expect: 100-continue 클라이언트는 본문을 보내기 전에 거절 사유를 받는다."""
    port, _ = live
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        c.putrequest("POST", "/api/upload/audio?auto=0")
        c.putheader("X-Filename", urllib.parse.quote("초대형.m4a"))
        c.putheader("Content-Length", str(900 * 1024 * 1024))  # 실제로 보내지 않는다
        c.putheader("Expect", "100-continue")
        c.endheaders()
        r = c.getresponse()
        assert r.status == 400
        assert "너무 큽니다" in json.loads(r.read())["error"]
    finally:
        c.close()


def test_unsupported_extension_rejected(live):
    port, _ = live
    status, res = _post_audio(port, "문서.pdf", b"%PDF-1.4")
    assert status == 400 and "지원하지 않는" in res["error"]


def test_raw_utf8_filename_header_survives(live):
    """URL 인코딩 없이 UTF-8 바이트로 보낸 한글 파일명도 되살린다(curl 등)."""
    port, _ = live
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        c.request(
            "POST", "/api/upload/audio?auto=0", body=b"fake",
            headers={"X-Filename": "회의 녹음.m4a".encode().decode("latin-1"),
                     "Content-Length": "4"},
        )
        res = json.loads(c.getresponse().read())
    finally:
        c.close()
    assert res["ok"] is True and res["name"] == "회의 녹음.m4a"
