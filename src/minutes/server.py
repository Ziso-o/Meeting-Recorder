"""minutes.server — 오케스트레이터(n8n 등)가 HTTP로 호출하는 얇은 서비스.

n8n의 Execute Command 노드는 버전에 따라 비활성/미지원이라 의존하지 않는다.
대신 이 서비스를 HTTP Request 노드로 호출한다. 표준 라이브러리만 사용(추가 의존성 없음).

실행:
    python -m minutes.server            # 기본 127.0.0.1:8900
    MINUTES_SERVER_PORT=9000 python -m minutes.server
    MINUTES_SERVER_HOST=0.0.0.0 ...     # 외부 노출(클라우드) 시에만

엔드포인트(모두 JSON):
    GET  /health
    POST /bot/dispatch   {platform?, meeting|meetingId, language?}
    POST /bot/stop       {platform?, meeting|meetingId}
    POST /ingest         {platform?, meeting|meetingId, profile?, out?, title?, date?, glossary?}
    POST /pipeline       {audio, profile?, out?, title?, date?, glossary?}
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .chain import generate_minutes
from .config import load_dotenv, provider_for_profile
from .glossary import load_glossary
from .render import render_markdown
from .vexa import select_vexa_client, vexa_to_segments


def _meeting(body: dict) -> str:
    m = body.get("meeting") or body.get("meetingId") or body.get("native_meeting_id")
    if not m:
        raise KeyError("meeting/meetingId")
    return str(m)


def _default_stem(profile: str, meeting: str) -> str:
    home = os.environ.get("MINUTES_HOME", ".")
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in meeting)
    return str(Path(home) / "data" / "out" / profile / f"vexa_{safe}")


def _write(stem: str, meta: dict, segments: list, minutes) -> None:
    p = Path(stem)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.with_suffix(".transcript.json").write_text(
        json.dumps(
            {"meta": {k: v for k, v in meta.items() if v},
             "segments": [s.model_dump() for s in segments]},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    p.with_suffix(".minutes.json").write_text(
        json.dumps(minutes.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    p.with_suffix(".minutes.md").write_text(render_markdown(minutes), encoding="utf-8")


def _result(stem: str, segments: list, minutes) -> dict:
    return {
        "ok": True,
        "stem": str(stem),
        "minutes_md": f"{stem}.minutes.md",
        "segments": len(segments),
        "decisions": len(minutes.decisions),
        "action_items": len(minutes.action_items),
    }


# ---- 엔드포인트 핸들러 ----
def ep_health(_body: dict) -> dict:
    return {"ok": True, "service": "minutes.server"}


def ep_bot_dispatch(body: dict) -> dict:
    client = select_vexa_client()
    return client.request_bot(
        body.get("platform", "google_meet"), _meeting(body), language=body.get("language", "ko")
    )


def ep_bot_stop(body: dict) -> dict:
    client = select_vexa_client()
    return client.stop_bot(body.get("platform", "google_meet"), _meeting(body))


def ep_ingest(body: dict) -> dict:
    platform = body.get("platform", "google_meet")
    meeting = _meeting(body)
    profile = body.get("profile", "internal")
    client = select_vexa_client()
    segments = vexa_to_segments(client.get_transcript(platform, meeting))
    if not segments:
        raise ValueError("Vexa 전사에서 세그먼트를 찾지 못함")
    glossary = load_glossary(body.get("glossary", "glossary.yaml"))
    meta = {"meeting_title": body.get("title", ""), "date": body.get("date", ""),
            "source": f"vexa:{meeting}"}
    minutes = generate_minutes(segments, provider_for_profile(profile), glossary=glossary, meta=meta)
    stem = body.get("out") or _default_stem(profile, meeting)
    _write(stem, meta, segments, minutes)
    return _result(stem, segments, minutes)


def ep_pipeline(body: dict) -> dict:
    from .transcribe import transcribe_audio

    audio = body["audio"]
    profile = body.get("profile", "secure")
    glossary_path = body.get("glossary", "glossary.yaml")
    segments = transcribe_audio(audio, glossary_path)
    glossary = load_glossary(glossary_path)
    meta = {"meeting_title": body.get("title", ""), "date": body.get("date", ""),
            "source_audio": Path(audio).name}
    minutes = generate_minutes(segments, provider_for_profile(profile), glossary=glossary, meta=meta)
    stem = body.get("out") or str(Path(audio).with_suffix(""))
    _write(stem, meta, segments, minutes)
    return _result(stem, segments, minutes)


ROUTES: dict[tuple[str, str], Callable[[dict], dict]] = {
    ("GET", "/health"): ep_health,
    ("POST", "/bot/dispatch"): ep_bot_dispatch,
    ("POST", "/bot/stop"): ep_bot_stop,
    ("POST", "/ingest"): ep_ingest,
    ("POST", "/pipeline"): ep_pipeline,
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self, method: str) -> None:
        path = self.path.split("?", 1)[0]
        handler = ROUTES.get((method, path))
        if handler is None:
            self._send(404, {"ok": False, "error": f"no route {method} {path}"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw) if raw else {}
            result = handler(body)
            self._send(200, result)
        except KeyError as e:
            self._send(400, {"ok": False, "error": f"필수 필드 누락: {e}"})
        except Exception as e:  # 복구 가능: 오류를 JSON으로 반환(오케스트레이터가 재시도/알림)
            self._send(500, {"ok": False, "error": str(e)})

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[minutes.server] {self.address_string()} {fmt % args}")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    host = os.environ.get("MINUTES_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("MINUTES_SERVER_PORT", "8900"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"minutes.server 시작: http://{host}:{port}  (Ctrl+C 종료)")
    print("  라우트:", ", ".join(f"{m} {p}" for (m, p) in ROUTES))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
