"""minutes.server — HTTP 서비스 + 웹 대시보드.

n8n 등 오케스트레이터가 HTTP Request로 호출하고, 사람이 브라우저로 쓸 수 있는
간단한 대시보드(왼쪽 네비: 참석 / 상태 / 녹취파일 / 회의록)를 제공한다.
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
    POST /bot/dispatch     {url} 또는 {platform?, meeting|meetingId}
    POST /bot/stop         {platform?, meeting|meetingId}
    POST /ingest           {platform?, meeting|meetingId, profile?, out?, title?, date?, glossary?}
    POST /pipeline         {audio, profile?, out?, title?, date?, glossary?}
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .chain import generate_minutes
from .config import load_dotenv, provider_for_profile
from .glossary import load_glossary
from .render import render_markdown
from .vexa import parse_meeting_url, select_vexa_client, vexa_to_segments


def _data_dir() -> Path:
    return Path(os.environ.get("MINUTES_HOME", ".")) / "data"


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


# ---- 엔드포인트 핸들러(params = GET 쿼리 또는 POST JSON 바디) ----
def ep_health(_p: dict) -> dict:
    return {"ok": True, "service": "minutes.server"}


def ep_status(_p: dict) -> dict:
    try:
        vexa = select_vexa_client().bot_status()
    except Exception as e:  # Vexa 미기동 등 — 대시보드가 죽지 않게 오류를 값으로
        vexa = {"error": str(e)}
    return {"ok": True, "vexa": vexa}


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


def ep_file(p: dict) -> dict:
    rel = p.get("path") or ""
    if not rel:
        raise KeyError("path")
    root = _data_dir().resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(root):  # 경로 탈출 방지
        raise ValueError("허용되지 않은 경로")
    if not target.is_file():
        raise ValueError("파일을 찾을 수 없음")
    return {"ok": True, "path": rel, "name": target.name,
            "content": target.read_text(encoding="utf-8", errors="replace")}


def ep_bot_dispatch(body: dict) -> dict:
    passcode = body.get("passcode", "")
    if body.get("url"):
        parsed = parse_meeting_url(body["url"])
        platform = parsed["platform"]
        meeting = parsed["native_meeting_id"]
        passcode = passcode or parsed.get("passcode", "")
    else:
        platform = body.get("platform", "google_meet")
        meeting = _meeting(body)
    client = select_vexa_client()
    return client.request_bot(platform, meeting, language=body.get("language", "ko"), passcode=passcode)


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
    ("GET", "/api/status"): ep_status,
    ("GET", "/api/files"): ep_files,
    ("GET", "/api/file"): ep_file,
    ("POST", "/bot/dispatch"): ep_bot_dispatch,
    ("POST", "/bot/stop"): ep_bot_stop,
    ("POST", "/ingest"): ep_ingest,
    ("POST", "/pipeline"): ep_pipeline,
}


INDEX_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>회의록 봇 대시보드</title>
<style>
 *{box-sizing:border-box} body{margin:0;font-family:system-ui,'Segoe UI',sans-serif;color:#1f2937;background:#f8fafc}
 .app{display:flex;min-height:100vh}
 nav{width:200px;background:#111827;color:#e5e7eb;padding:16px 0;flex-shrink:0}
 nav h1{font-size:15px;padding:0 16px 12px;margin:0;border-bottom:1px solid #374151;color:#fff}
 nav a{display:block;padding:11px 16px;color:#cbd5e1;text-decoration:none;cursor:pointer;font-size:14px}
 nav a:hover{background:#1f2937} nav a.on{background:#2563eb;color:#fff}
 main{flex:1;padding:24px;max-width:900px}
 h2{font-size:18px;margin:0 0 16px} .view{display:none} .view.on{display:block}
 input,select,button,textarea{font-size:14px;padding:9px;border:1px solid #d1d5db;border-radius:6px}
 input,textarea{width:100%} button{background:#2563eb;color:#fff;border:0;cursor:pointer;padding:9px 16px}
 button.g{background:#e5e7eb;color:#111827} .row{display:flex;gap:8px;margin:8px 0;flex-wrap:wrap}
 pre{background:#fff;border:1px solid #e5e7eb;padding:14px;border-radius:8px;white-space:pre-wrap;word-break:break-all;font-size:13px}
 table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden}
 th,td{text-align:left;padding:9px 12px;border-bottom:1px solid #f1f5f9;font-size:13px}
 th{background:#f8fafc} tr:hover td{background:#f8fafc} .lnk{color:#2563eb;cursor:pointer}
 .badge{font-size:11px;padding:2px 7px;border-radius:99px;background:#e0e7ff;color:#3730a3}
 .muted{color:#6b7280;font-size:12px}
</style></head><body><div class="app">
<nav>
 <h1>🤖 회의록 봇</h1>
 <a data-v="join" class="on" onclick="go('join')">▶ 회의 참석</a>
 <a data-v="status" onclick="go('status')">📡 상태 모니터링</a>
 <a data-v="transcript" onclick="go('transcript')">🎙 녹취파일</a>
 <a data-v="minutes" onclick="go('minutes')">📄 회의록</a>
</nav>
<main>
 <section id="join" class="view on">
  <h2>회의 참석</h2>
  <p class="muted">회의 링크를 붙여넣으면 봇이 참석합니다 (Meet/Zoom/Teams/Jitsi).</p>
  <div class="row"><input id="url" placeholder="https://meet.google.com/abc-defg-hij">
   <button onclick="call('/bot/dispatch',{url:val('url')})">봇 참석</button></div>
  <h2 style="margin-top:28px">회의록 생성 (회의 종료 후)</h2>
  <div class="row"><input id="mid" placeholder="회의 ID (예: abc-defg-hij)" style="flex:1">
   <select id="profile"><option value="secure">secure(로컬)</option><option value="internal">internal</option></select>
   <button onclick="call('/ingest',{meeting:val('mid'),profile:val('profile')})">회의록 생성</button>
   <button class="g" onclick="call('/bot/stop',{meeting:val('mid')})">봇 종료</button></div>
  <h2 style="margin-top:20px">결과</h2><pre id="out">대기 중…</pre>
 </section>

 <section id="status" class="view">
  <h2>상태 모니터링 <button class="g" onclick="loadStatus()">새로고침</button></h2>
  <p class="muted">Vexa 봇 상태(GET /api/status). Vexa 미기동이면 error가 표시됩니다.</p>
  <pre id="statusOut">새로고침을 누르세요.</pre>
 </section>

 <section id="transcript" class="view">
  <h2>녹취파일 <button class="g" onclick="loadFiles('transcript')">새로고침</button></h2>
  <div id="transcriptList"></div><pre id="transcriptView" class="muted">파일을 선택하세요.</pre>
 </section>

 <section id="minutes" class="view">
  <h2>회의록 <button class="g" onclick="loadFiles('minutes')">새로고침</button></h2>
  <div id="minutesList"></div><pre id="minutesView" class="muted">파일을 선택하세요.</pre>
 </section>
</main></div>
<script>
 const val=id=>document.getElementById(id).value.trim();
 function go(v){document.querySelectorAll('.view').forEach(s=>s.classList.toggle('on',s.id===v));
   document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('on',a.dataset.v===v));
   if(v==='status')loadStatus(); if(v==='transcript')loadFiles('transcript'); if(v==='minutes')loadFiles('minutes');}
 async function call(path,body){const o=document.getElementById('out');o.textContent='요청 중…';
   try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
     o.textContent=JSON.stringify(await r.json(),null,2);}catch(e){o.textContent='오류: '+e}}
 async function loadStatus(){const o=document.getElementById('statusOut');o.textContent='조회 중…';
   try{const r=await fetch('/api/status');o.textContent=JSON.stringify(await r.json(),null,2);}catch(e){o.textContent='오류: '+e}}
 async function loadFiles(kind){const box=document.getElementById(kind+'List');box.innerHTML='조회 중…';
   try{const r=await fetch('/api/files');const d=await r.json();
     const rows=(d.files||[]).filter(f=>f.kind===kind);
     if(!rows.length){box.innerHTML='<p class="muted">파일이 없습니다. (data/out 확인)</p>';return;}
     box.innerHTML='<table><tr><th>파일</th><th>수정</th><th>크기</th></tr>'+rows.map(f=>
       `<tr><td><span class="lnk" onclick="viewFile('${kind}','${f.path}')">${f.name}</span></td>
        <td class="muted">${new Date(f.mtime*1000).toLocaleString()}</td><td class="muted">${f.size}B</td></tr>`).join('')+'</table>';
   }catch(e){box.innerHTML='오류: '+e}}
 async function viewFile(kind,path){const v=document.getElementById(kind+'View');v.textContent='불러오는 중…';v.className='';
   try{const r=await fetch('/api/file?path='+encodeURIComponent(path));const d=await r.json();
     v.textContent=d.content!==undefined?d.content:JSON.stringify(d,null,2);}catch(e){v.textContent='오류: '+e}}
</script></body></html>"""


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
        except Exception as e:  # 복구 가능: 오류를 JSON으로 반환
            self._send(500, {"ok": False, "error": str(e)})

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path in ("/", "/index.html"):
            self._send_html(INDEX_HTML)
            return
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
    print(f"  웹 대시보드: http://{host}:{port}/   (참석 / 상태 / 녹취파일 / 회의록)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
