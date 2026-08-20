"""OllamaProvider 스트리밍 — 폭주 차단 · 무응답 감지 · 잘림 경고.

실제로 겪은 실패: 같은 크기의 청크인데 하나는 80초, 다른 하나는 1800초 초과.
속도가 아니라 **반복 생성 폭주**였고, 통짜 요청(stream=False)이라 알아챌 수도
막을 수도 없었다. 여기서는 로컬 HTTP 서버로 그 상황을 재현한다.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from minutes.providers.ollama import OllamaProvider


class _FakeOllama(BaseHTTPRequestHandler):
    """/api/generate 를 흉내낸다. 동작은 클래스 속성 mode 로 고른다."""

    mode = "ok"
    seen: ClassVar[dict] = {}

    def log_message(self, *a):  # 조용히
        return

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen = body
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()

        def emit(**kw):
            self.wfile.write((json.dumps(kw) + "\n").encode())
            self.wfile.flush()

        try:
            if self.mode == "ok":
                for w in ("회의록", " 작성함"):
                    emit(response=w, done=False)
                emit(response="", done=True, done_reason="stop")
            elif self.mode == "truncated":          # 출력 상한에 걸림
                emit(response="잘린 요약", done=False)
                emit(response="", done=True, done_reason="length")
            elif self.mode == "runaway":            # 반복 생성 폭주
                while True:
                    emit(response="같은 말 ", done=False)
                    time.sleep(0.002)
            elif self.mode == "stalled":            # 토큰이 안 옴
                emit(response="시작", done=False)
                time.sleep(30)
            elif self.mode == "error":
                emit(error="model not found")
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOllama)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_streaming_returns_full_text(server):
    _FakeOllama.mode = "ok"
    p = OllamaProvider(host=server, model="qwen2.5:3b")
    assert p.generate("회의 내용") == "회의록 작성함"


def test_request_carries_runaway_guards(server):
    """폭주를 막는 옵션이 실제 요청에 실려야 의미가 있다."""
    _FakeOllama.mode = "ok"
    OllamaProvider(host=server, model="qwen2.5:3b").generate("가" * 3000)
    opts = _FakeOllama.seen["options"]
    assert opts["num_predict"] == 2048          # 출력 상한
    assert opts["repeat_penalty"] > 1.0         # 반복 억제
    assert opts["num_ctx"] == 8192              # 프롬프트에 맞춘 컨텍스트
    assert _FakeOllama.seen["stream"] is True
    assert _FakeOllama.seen["keep_alive"]       # 청크마다 모델 재로딩 방지


def test_num_predict_is_configurable(server, monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_PREDICT", "512")
    _FakeOllama.mode = "ok"
    OllamaProvider(host=server).generate("짧은 입력")
    assert _FakeOllama.seen["options"]["num_predict"] == 512


def test_truncated_output_is_reported(server, capsys):
    """상한에 걸려 잘리면 조용히 넘어가지 않는다 — 회의록 뒷부분이 사라진다."""
    _FakeOllama.mode = "truncated"
    OllamaProvider(host=server).generate("회의 내용")
    assert "잘렸습니다" in capsys.readouterr().out


def test_runaway_is_stopped_by_wall_clock(server):
    """폭주하면 전체 상한에서 끊고, 얼마나 생성했는지 알려준다."""
    _FakeOllama.mode = "runaway"
    p = OllamaProvider(host=server, model="qwen2.5:3b", timeout=2.0)
    started = time.monotonic()
    with pytest.raises(TimeoutError) as ei:
        p.generate("회의 내용")
    assert time.monotonic() - started < 15          # 1800초를 기다리지 않는다
    msg = str(ei.value)
    assert "생성" in msg and "토큰" in msg


def test_stalled_model_detected_fast(server, monkeypatch):
    """토큰이 끊기면 전체 타임아웃(30분)을 기다리지 않고 바로 잡는다."""
    monkeypatch.setenv("OLLAMA_STALL_TIMEOUT", "1")
    _FakeOllama.mode = "stalled"
    p = OllamaProvider(host=server, timeout=1800)   # 전체 상한은 크게 둬도
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        p.generate("회의 내용")
    assert time.monotonic() - started < 15          # 토큰 간격으로 먼저 걸린다


def test_error_line_surfaces(server):
    _FakeOllama.mode = "error"
    with pytest.raises(RuntimeError, match="model not found"):
        OllamaProvider(host=server).generate("회의 내용")


def test_diagnosis_distinguishes_failure_modes():
    """폭주와 무응답은 대처가 달라서 메시지도 달라야 한다."""
    p = OllamaProvider(model="qwen2.5:3b")
    t = time.monotonic() - 1800
    assert "반복" in p._slow_message("가" * 5000, t, p.num_predict)
    assert "메모리" in p._slow_message("가" * 5000, t, 0)
    assert "작은 모델" in p._slow_message("가" * 5000, t, 50)


def test_num_thread_only_sent_when_set(server, monkeypatch):
    """0이면 Ollama 기본에 맡긴다 — 잘못된 값을 억지로 밀어 넣지 않는다."""
    _FakeOllama.mode = "ok"
    monkeypatch.setenv("OLLAMA_NUM_THREAD", "0")
    OllamaProvider(host=server).generate("입력")
    assert "num_thread" not in _FakeOllama.seen["options"]

    monkeypatch.setenv("OLLAMA_NUM_THREAD", "8")
    OllamaProvider(host=server).generate("입력")
    assert _FakeOllama.seen["options"]["num_thread"] == 8


def test_bench_script_survives_no_ollama():
    """Ollama 가 안 떠 있어도 스크립트가 죽지 않고 안내를 낸다."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(
        [sys.executable, str(root / "scripts" / "bench_llm.py"),
         "--threads", "0", "--num-predict", "8"],
        capture_output=True, text=True, timeout=120, check=False,
        env={**__import__("os").environ, "OLLAMA_HOST": "http://127.0.0.1:1"},
    )
    assert out.returncode == 0, out.stderr[-1500:]
    assert "전원 모드" in out.stdout        # 느릴 때 확인할 것들을 안내
