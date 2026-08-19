"""minutes.server — HTTP 서비스 + 웹 대시보드.

n8n 등 오케스트레이터가 HTTP Request로 호출하고, 사람이 브라우저로 쓸 수 있는
대시보드(왼쪽 네비: 참석 / 상태 / 녹취파일 / 회의록)를 제공한다.
표준 라이브러리만 사용(추가 의존성 없음).

실행:
    python -m minutes.server            # 기본 127.0.0.1:8900, 웹 UI: http://127.0.0.1:8900/
    MINUTES_SERVER_PORT=9000 python -m minutes.server
    MINUTES_SERVER_HOST=0.0.0.0 ...     # 외부 노출(클라우드) 시에만

엔드포인트:
    GET  /                 웹 대시보드(HTML)
    GET  /health
    GET  /api/status       Vexa 봇 상태
    GET  /api/files        data/ 아래 전사·회의록 파일 목록
    GET  /api/file?path=   파일 내용(data/ 내부만)
    POST /mode             {mock: true|false}  흉내↔실제 전환(프로세스 한정, .env 불변)
    POST /bot/dispatch     {url} 또는 {platform?, meeting|meetingId}
    POST /bot/stop         {platform?, meeting|meetingId}
    POST /ingest           {platform?, meeting|meetingId, profile?, out?, title?, date?, glossary?}
    POST /pipeline         {audio, profile?, out?, title?, date?, glossary?}
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ._webui import INDEX_HTML
from .chain import generate_minutes
from .config import load_dotenv, provider_for_profile
from .glossary import load_glossary
from .render import render_markdown
from .vexa import parse_meeting_url, select_vexa_client, vexa_to_segments


def _data_dir() -> Path:
    return Path(os.environ.get("MINUTES_HOME", ".")) / "data"


_MOCK_KEYS = ("VEXA_CLIENT", "LLM_PROVIDER", "ASR_ENGINE", "DIARIZER")
_baseline: dict[str, str | None] | None = None  # 서버 시작 시점(.env 반영)의 원래 값


def _mock_flags() -> dict:
    """어떤 하위 시스템이 흉내(mock) 모드인지 — 대시보드가 배지로 알려주기 위함."""
    def m(k: str) -> bool:
        return os.environ.get(k, "").lower() == "mock"

    v, llm, asr, dia = (m(k) for k in _MOCK_KEYS)
    return {"vexa": v, "llm": llm, "asr": asr, "diarizer": dia,
            "any": v or llm or asr or dia}


def _capture_baseline() -> None:
    global _baseline
    if _baseline is None:
        _baseline = {k: os.environ.get(k) for k in _MOCK_KEYS}


def _meeting(body: dict) -> str:
    m = body.get("meeting") or body.get("meetingId") or body.get("native_meeting_id")
    if not m:
        raise KeyError("meeting/meetingId")
    return str(m)


def _infer_platform(meeting: str) -> str:
    """링크 없이 ID만 들어왔을 때 형태로 플랫폼을 추정한다(추정 실패 시 google_meet)."""
    if re.fullmatch(r"[a-z]{3}-[a-z]{4}-[a-z]{3}", meeting):
        return "google_meet"            # abc-defg-hij
    if re.fullmatch(r"\d{9,11}", meeting):
        return "zoom"                    # 85130931937
    return "google_meet"


def _resolve_target(body: dict) -> tuple[str, str]:
    """회의 링크(url) 또는 platform+meeting 에서 (platform, native_meeting_id)를 뽑는다.

    url이 있으면 거기서 플랫폼까지 자동 인식(zoom/teams/meet/jitsi 공통).
    링크 없이 ID만 있으면 body의 platform → 없으면 ID 형태로 추정.
    """
    if body.get("url"):
        parsed = parse_meeting_url(body["url"])
        return parsed["platform"], parsed["native_meeting_id"]
    meeting = _meeting(body)
    return body.get("platform") or _infer_platform(meeting), meeting


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


# ---- 엔드포인트 핸들러(params = GET 쿼리 또는 POST JSON 바디) ----
def ep_health(_p: dict) -> dict:
    return {"ok": True, "service": "minutes.server", "mock": _mock_flags()}


def ep_status(_p: dict) -> dict:
    try:
        vexa = select_vexa_client().bot_status()
    except Exception as e:  # noqa: BLE001  Vexa 미기동 등 — 대시보드가 죽지 않게 오류를 값으로
        vexa = {"error": str(e)}
    return {"ok": True, "vexa": vexa, "mock": _mock_flags()}


def ep_files(_p: dict) -> dict:
    root = _data_dir()
    items: list[dict] = []
    if root.exists():
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            name = p.name
            if name.endswith(".minutes.md"):
                kind = "minutes"
            elif name.endswith(".transcript.json"):
                kind = "transcript"
            else:
                continue
            st = p.stat()
            items.append({
                "path": str(p.relative_to(root)).replace("\\", "/"),
                "name": name, "kind": kind, "size": st.st_size, "mtime": int(st.st_mtime),
            })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return {"ok": True, "files": items}


def _safe_target(rel: str) -> Path:
    """data/ 내부 경로만 허용(경로 탈출 방지)."""
    if not rel:
        raise KeyError("path")
    root = _data_dir().resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        raise ValueError("허용되지 않은 경로")
    return target


def _kind_suffix(kind: str) -> str:
    return ".minutes.md" if kind == "minutes" else ".transcript.json"


def _safe_stem(name: str) -> str:
    """파일명에서 안전한 stem 추출(경로·확장자 제거, 위험문자 정리)."""
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    for suf in (".minutes.md", ".transcript.json", ".md", ".json", ".txt"):
        if base.lower().endswith(suf):
            base = base[: -len(suf)]
            break
    base = "".join(c if (c.isalnum() or c in " -_.()[]") else "_" for c in base).strip()
    return base or "untitled"


def ep_file(p: dict) -> dict:
    target = _safe_target(p.get("path") or "")
    if not target.is_file():
        raise ValueError("파일을 찾을 수 없음")
    return {"ok": True, "path": p.get("path"), "name": target.name,
            "content": target.read_text(encoding="utf-8", errors="replace")}


def _is_managed(name: str) -> bool:
    return name.endswith((".minutes.md", ".transcript.json"))


def ep_upload(body: dict) -> dict:
    kind = "minutes" if body.get("kind") == "minutes" else "transcript"
    content = body.get("content", "")
    if len(content) > 5_000_000:
        raise ValueError("파일이 너무 큽니다(5MB 초과)")
    stem = _safe_stem(body.get("name", "untitled"))
    d = _data_dir() / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    target = d / (stem + _kind_suffix(kind))
    i = 1  # 덮어쓰기 방지: 같은 이름이면 (n) 붙임
    while target.exists():
        target = d / (f"{stem}({i})" + _kind_suffix(kind))
        i += 1
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(target.relative_to(_data_dir())).replace("\\", "/")}


def ep_delete(body: dict) -> dict:
    target = _safe_target(body.get("path") or "")
    if not target.is_file():
        raise ValueError("파일을 찾을 수 없음")
    if not _is_managed(target.name):
        raise ValueError("삭제할 수 없는 파일 형식")
    target.unlink()
    return {"ok": True}


def ep_rename(body: dict) -> dict:
    target = _safe_target(body.get("path") or "")
    new = body.get("name", "")
    if not new:
        raise KeyError("name")
    if not target.is_file() or not _is_managed(target.name):
        raise ValueError("이름을 바꿀 수 없는 파일")
    kind = "minutes" if target.name.endswith(".minutes.md") else "transcript"
    dest = target.parent / (_safe_stem(new) + _kind_suffix(kind))
    if dest.exists() and dest != target:
        raise ValueError("같은 이름이 이미 있습니다")
    target.rename(dest)
    return {"ok": True, "path": str(dest.relative_to(_data_dir())).replace("\\", "/")}


def ep_mode(body: dict) -> dict:
    """흉내(mock) ↔ 실제 모드 전환. 이 서버 프로세스가 켜져 있는 동안에만 적용된다.
    (.env 파일은 건드리지 않음 — 재시작하면 .env 값으로 돌아감.)
    """
    _capture_baseline()
    want = body.get("mock")
    if want is None:
        raise KeyError("mock")
    assert _baseline is not None
    for k in _MOCK_KEYS:
        if want:
            os.environ[k] = "mock"
        else:  # 실제: 원래 값이 mock이 아니면 복원, mock이었으면 제거(=실제 기본값)
            base = _baseline.get(k)
            if base and base.lower() != "mock":
                os.environ[k] = base
            else:
                os.environ.pop(k, None)
    return {"ok": True, "mock": _mock_flags()}


# ---- 참석 회의 추적 → 회의 끝나면 자동 회의록 (폴링) ----
_TRACKED: dict[tuple[str, str], dict] = {}
_TLOCK = threading.Lock()


def _track(platform: str, meeting: str, profile: str, title: str) -> None:
    with _TLOCK:
        _TRACKED[(platform, meeting)] = {
            "platform": platform, "meeting": meeting, "profile": profile, "title": title,
            "status": "waiting", "seen": False, "since": time.time(), "stem": "", "error": "",
        }


def _running_keys(status: dict) -> set[tuple[str, str]]:
    """Vexa bot_status 응답에서 (platform, meeting) 집합을 뽑는다(형태 관대하게)."""
    bots = status.get("running_bots") or status.get("running") or status.get("bots") or []
    keys: set[tuple[str, str]] = set()
    for b in bots if isinstance(bots, list) else []:
        if isinstance(b, dict):
            p = b.get("platform") or b.get("platform_name")
            m = b.get("native_meeting_id") or b.get("meeting") or b.get("meeting_id") or b.get("id")
            if p and m:
                keys.add((str(p), str(m)))
    return keys


def ep_bot_dispatch(body: dict) -> dict:
    passcode = body.get("passcode", "")
    meeting_url = ""
    if body.get("url"):
        meeting_url = body["url"]  # zoom/jitsi는 전체 링크가 필요(패스워드도 링크에 포함)
        parsed = parse_meeting_url(body["url"])
        platform = parsed["platform"]
        meeting = parsed["native_meeting_id"]
        passcode = passcode or parsed.get("passcode", "")
    else:
        platform = body.get("platform", "google_meet")
        meeting = _meeting(body)
    client = select_vexa_client()
    res = client.request_bot(platform, meeting, language=body.get("language", "ko"),
                             passcode=passcode, meeting_url=meeting_url)
    # 자동 회의록: 참석 성공 시 회의를 추적 목록에 등록(회의 끝나면 워처가 생성)
    if body.get("auto", True) and str(res.get("status", "")).lower() != "error":
        _track(platform, meeting, body.get("profile", "secure"), body.get("title", ""))
    return res


def ep_tracked(_p: dict) -> dict:
    with _TLOCK:
        items = sorted(_TRACKED.values(), key=lambda x: x["since"], reverse=True)
        return {"ok": True, "tracked": [dict(x) for x in items]}


def ep_bot_stop(body: dict) -> dict:
    platform, meeting = _resolve_target(body)
    client = select_vexa_client()
    return client.stop_bot(platform, meeting)


def _generate(platform: str, meeting: str, profile: str, *, out: str = "",
              title: str = "", date: str = "", glossary_path: str = "glossary.yaml") -> dict:
    """Vexa 전사 → 회의록 생성(수동 ingest·자동 워처 공용)."""
    client = select_vexa_client()
    segments = vexa_to_segments(client.get_transcript(platform, meeting))
    if not segments:
        raise ValueError("Vexa 전사에서 세그먼트를 찾지 못함")
    glossary = load_glossary(glossary_path)
    meta = {"meeting_title": title, "date": date, "source": f"vexa:{meeting}"}
    minutes = generate_minutes(segments, provider_for_profile(profile), glossary=glossary, meta=meta)
    stem = out or _default_stem(profile, meeting)
    _write(stem, meta, segments, minutes)
    return _result(stem, segments, minutes)


def ep_ingest(body: dict) -> dict:
    platform, meeting = _resolve_target(body)
    return _generate(platform, meeting, body.get("profile", "internal"),
                     out=body.get("out", ""), title=body.get("title", ""),
                     date=body.get("date", ""), glossary_path=body.get("glossary", "glossary.yaml"))


def _watch_once() -> None:
    """추적 중 회의를 1회 점검: 봇이 나갔으면(회의 종료) 자동으로 회의록 생성."""
    try:
        status = select_vexa_client().bot_status()
    except Exception:  # noqa: BLE001
        return
    running = _running_keys(status)
    with _TLOCK:
        targets = list(_TRACKED.items())
    for key, t in targets:
        if t["status"] in ("done", "failed", "timeout"):
            continue
        if key in running:
            with _TLOCK:
                t["status"], t["seen"] = "live", True
        elif t["seen"]:  # 참석했다가 사라짐 = 회의 종료 → 생성
            try:
                r = _generate(t["platform"], t["meeting"], t["profile"], title=t["title"])
                with _TLOCK:
                    t["status"], t["stem"] = "done", r["stem"]
            except Exception as e:  # noqa: BLE001  전사 아직 없음 등 — 다음 주기에 재시도되지 않게 실패 표시
                with _TLOCK:
                    t["status"], t["error"] = "failed", str(e)
        elif time.time() - t["since"] > 900:  # 15분간 참석 확인 안 됨 → 타임아웃
            with _TLOCK:
                t["status"] = "timeout"


def _watch_loop(interval: float = 20.0) -> None:
    while True:
        _watch_once()
        time.sleep(interval)


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
    ("GET", "/api/status"): ep_status,
    ("GET", "/api/files"): ep_files,
    ("GET", "/api/file"): ep_file,
    ("GET", "/api/tracked"): ep_tracked,
    ("POST", "/api/upload"): ep_upload,
    ("POST", "/api/delete"): ep_delete,
    ("POST", "/api/rename"): ep_rename,
    ("POST", "/mode"): ep_mode,
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

    def _send_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        handler = ROUTES.get((method, parsed.path))
        if handler is None:
            self._send(404, {"ok": False, "error": f"no route {method} {parsed.path}"})
            return
        try:
            if method == "GET":
                params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            else:
                length = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(length) if length else b""
                params = json.loads(raw) if raw else {}
            self._send(200, handler(params))
        except KeyError as e:
            self._send(400, {"ok": False, "error": f"필수 필드 누락: {e}"})
        except Exception as e:  # noqa: BLE001  복구 가능: 오류를 JSON으로 반환
            self._send(500, {"ok": False, "error": str(e)})

    def do_GET(self) -> None:
        if urlparse(self.path).path in ("/", "/index.html"):
            self._send_html(INDEX_HTML)
            return
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[minutes.server] {self.address_string()} {fmt % args}")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    _capture_baseline()  # .env 반영된 원래 값을 기억(웹 모드전환의 '실제' 기준)
    host = os.environ.get("MINUTES_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("MINUTES_SERVER_PORT", "8900"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=_watch_loop, daemon=True).start()  # 회의 끝나면 자동 회의록
    print(f"minutes.server 시작: http://{host}:{port}  (Ctrl+C 종료)")
    print(f"  웹 대시보드: http://{host}:{port}/   (참석 / 상태 / 녹취파일 / 회의록)")
    print("  자동 회의록: 참석한 회의가 끝나면 워처가 전사→회의록을 자동 생성합니다.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
