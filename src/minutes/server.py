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
    GET  /api/files        data/ 아래 전사·회의록·녹음본 파일 목록
    GET  /api/file?path=   파일 내용(data/ 내부만, 텍스트만)
    GET  /api/jobs         녹음본 처리(전사→회의록) 작업 진행 상황
    POST /mode             {mock: true|false}  흉내↔실제 전환(프로세스 한정, .env 불변)
    POST /bot/dispatch     {url} 또는 {platform?, meeting|meetingId}
    POST /bot/stop         {platform?, meeting|meetingId}
    POST /ingest           {platform?, meeting|meetingId, profile?, out?, title?, date?, glossary?}
    POST /pipeline         {audio, profile?, out?, title?, date?, glossary?}
    POST /api/upload/audio 녹음본 업로드(raw 바이너리 스트리밍) — 아래 참고

녹음본 업로드는 JSON이 아니라 **파일 바이트를 그대로** 본문에 담는다(base64·메모리 버퍼 없음).
파일명·옵션은 헤더/쿼리로 넘긴다:

    POST /api/upload/audio?profile=secure&auto=1&title=%EC%A0%9C%EB%AA%A9
    X-Filename: %EA%B0%9C%EB%B0%9C%ED%9A%8C%EC%9D%98.m4a   (URL 인코딩)
    Content-Type: application/octet-stream
    <파일 바이트>

auto=1이면 업로드 직후 백그라운드로 전사→회의록까지 만들고, 진행 상황은 GET /api/jobs 로 본다.
크기 상한은 MINUTES_MAX_UPLOAD_MB(녹음본, 기본 500) / MINUTES_MAX_TEXT_UPLOAD_MB(텍스트, 기본 5).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from ._webui import INDEX_HTML
from .audio_formats import AUDIO_EXTS, audio_ext, is_audio_name
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
    return {"ok": True, "service": "minutes.server", "mock": _mock_flags(),
            "limits": {"audio_mb": _max_upload_bytes("audio") // (1024 * 1024),
                       "text_mb": _max_upload_bytes("text") // (1024 * 1024)}}


def ep_status(_p: dict) -> dict:
    try:
        vexa = select_vexa_client().bot_status()
    except Exception as e:  # noqa: BLE001  Vexa 미기동 등 — 대시보드가 죽지 않게 오류를 값으로
        vexa = {"error": str(e)}
    return {"ok": True, "vexa": vexa, "mock": _mock_flags()}


def _file_kind(name: str) -> str | None:
    """관리 대상 파일이면 종류를, 아니면 None."""
    if name.endswith(".minutes.md"):
        return "minutes"
    if name.endswith(".transcript.json"):
        return "transcript"
    if is_audio_name(name):
        return "audio"
    return None


def ep_files(_p: dict) -> dict:
    root = _data_dir()
    items: list[dict] = []
    if root.exists():
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            kind = _file_kind(p.name)
            if kind is None:
                continue
            st = p.stat()
            items.append({
                "path": str(p.relative_to(root)).replace("\\", "/"),
                "name": p.name, "kind": kind, "size": st.st_size, "mtime": int(st.st_mtime),
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


def _managed_suffix(name: str) -> str:
    """관리 대상 파일의 '유지해야 할 확장자'. 오디오는 원본 확장자를 그대로 지킨다."""
    low = name.lower()
    if low.endswith(".minutes.md"):
        return ".minutes.md"
    if low.endswith(".transcript.json"):
        return ".transcript.json"
    ext = Path(name).suffix.lower()
    return ext if ext in AUDIO_EXTS else ""


def _safe_stem(name: str) -> str:
    """파일명에서 안전한 stem 추출(경로·확장자 제거, 위험문자 정리)."""
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    for suf in (".minutes.md", ".transcript.json", ".md", ".json", ".txt", *AUDIO_EXTS):
        if base.lower().endswith(suf):
            base = base[: -len(suf)]
            break
    base = "".join(c if (c.isalnum() or c in " -_.()[]") else "_" for c in base).strip()
    return base or "untitled"


def _unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """같은 이름이 있으면 (1), (2)… 를 붙여 덮어쓰기를 막는다."""
    target = directory / (stem + suffix)
    i = 1
    while target.exists():
        target = directory / f"{stem}({i}){suffix}"
        i += 1
    return target


def _max_upload_bytes(kind: str) -> int:
    """업로드 상한(바이트). 환경변수로 조정 가능.

    녹음본은 디스크로 스트리밍 저장하므로 크게 잡아도 메모리를 쓰지 않는다.
    텍스트(전사 JSON·회의록 MD)는 요청 본문을 통째로 메모리에 올리는 JSON 경로라
    보수적으로 유지한다.
    """
    if kind == "audio":
        return int(float(os.environ.get("MINUTES_MAX_UPLOAD_MB", "500")) * 1024 * 1024)
    return int(float(os.environ.get("MINUTES_MAX_TEXT_UPLOAD_MB", "5")) * 1024 * 1024)


def _too_big(kind: str) -> ValueError:
    mb = _max_upload_bytes(kind) / (1024 * 1024)
    label = "녹음본" if kind == "audio" else "파일"
    return ValueError(f"{label}이 너무 큽니다({mb:g}MB 초과)")


def _rel(target: Path) -> str:
    return str(target.relative_to(_data_dir())).replace("\\", "/")


def ep_file(p: dict) -> dict:
    target = _safe_target(p.get("path") or "")
    if not target.is_file():
        raise ValueError("파일을 찾을 수 없음")
    if is_audio_name(target.name):
        # 오디오는 텍스트가 아니다 — 깨진 문자열 대신 정확한 안내를 준다.
        raise ValueError("녹음본은 글로 볼 수 없어요. 회의록을 만들면 내용을 볼 수 있어요.")
    return {"ok": True, "path": p.get("path"), "name": target.name,
            "content": target.read_text(encoding="utf-8", errors="replace")}


def _is_managed(name: str) -> bool:
    return _file_kind(name) is not None


def ep_upload(body: dict) -> dict:
    """텍스트 업로드(전사 JSON / 회의록 MD). 녹음본은 POST /api/upload/audio 를 쓴다."""
    if body.get("kind") == "audio":
        raise ValueError("녹음본은 /api/upload/audio 로 올려 주세요")
    kind = "minutes" if body.get("kind") == "minutes" else "transcript"
    content = body.get("content", "")
    if len(content.encode("utf-8")) > _max_upload_bytes("text"):
        raise _too_big("text")
    d = _data_dir() / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    target = _unique_path(d, _safe_stem(body.get("name", "untitled")), _kind_suffix(kind))
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "kind": kind, "path": _rel(target)}


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
    dest = target.parent / (_safe_stem(new) + _managed_suffix(target.name))
    if dest.exists() and dest != target:
        raise ValueError("같은 이름이 이미 있습니다")
    target.rename(dest)
    return {"ok": True, "path": _rel(dest)}


# ---- 녹음본 업로드 (클로바 노트 m4a 등) → 전사·회의록 자동 생성 ----
#
# 텍스트 업로드와 달리 **본문 바이트를 읽는 즉시 디스크로 흘려보낸다**(청크 스트리밍).
# base64도, 통짜 메모리 버퍼도 쓰지 않으므로 큰 녹음본도 서버 메모리를 먹지 않는다.

_UPLOAD_CHUNK = 1024 * 1024        # 1MB
_DRAIN_LIMIT = 32 * 1024 * 1024    # 거부 후 이만큼까지는 본문을 읽어 버리고 정상 응답


def audio_upload_dir(auto: bool) -> Path:
    """auto=True: 서버가 직접 처리(uploads/audio). False: 외부 watch 가 집어가게(incoming).

    두 폴더를 나눠 `minutes.watch` 와 서버 작업이 같은 파일을 동시에 처리하는 일을 막는다.
    """
    return _data_dir() / ("uploads/audio" if auto else "incoming")


def save_audio_stream(
    name: str, reader, length: int, auto: bool = True, progress: dict | None = None
) -> Path:
    """업로드 스트림을 오디오 파일로 저장하고 최종 경로를 반환한다.

    reader: .read(n) 를 지원하는 객체(HTTP rfile / BytesIO).
    length: Content-Length. 선언값이 상한을 넘으면 **읽기 전에** 거부한다.
    progress: 넘기면 {"read": 지금까지 읽은 바이트} 를 갱신한다(거부 시 남은 본문 처리용).
    """
    ext = audio_ext(name)
    limit = _max_upload_bytes("audio")
    if length <= 0:
        raise ValueError("업로드할 내용이 없습니다(Content-Length 필요)")
    if length > limit:
        raise _too_big("audio")

    d = audio_upload_dir(auto)
    d.mkdir(parents=True, exist_ok=True)
    target = _unique_path(d, _safe_stem(name), ext)
    part = target.with_name(target.name + ".part")  # 완성 전에는 watch 가 못 집게
    written = 0
    try:
        with part.open("wb") as f:
            while written < length:
                chunk = reader.read(min(_UPLOAD_CHUNK, length - written))
                if not chunk:
                    break
                written += len(chunk)
                if progress is not None:
                    progress["read"] = written
                f.write(chunk)
        if written < length:
            raise ValueError(f"업로드가 중간에 끊겼어요({written}/{length} 바이트)")
        part.rename(target)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    return target


# ---- 녹음본 처리 작업(전사→회의록) — 백그라운드 + 진행상황 폴링 ----
#
# 실제 전사는 수 분~수십 분 걸린다. HTTP 응답을 붙잡고 있으면 브라우저가 타임아웃되므로
# 업로드 응답은 즉시 돌려주고, 진행 상황은 GET /api/jobs 로 확인한다.

_JOBS: dict[str, dict] = {}
_JLOCK = threading.Lock()
_JOBS_KEEP = 50  # 오래된 작업 기록은 이 개수만 남긴다
# 전사는 GPU·메모리를 크게 쓴다 — 동시에 여러 건이 돌지 않도록 한 줄로 세운다.
_RUN_LOCK = threading.Lock()


def _job_set(job_id: str, **fields: Any) -> None:
    with _JLOCK:
        job = _JOBS.get(job_id)
        if job is not None:
            job.update(fields)


def _job_add(audio: Path, profile: str, title: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _JLOCK:
        now = time.time()
        _JOBS[job_id] = {
            "id": job_id, "name": audio.name, "audio": _rel(audio), "profile": profile,
            "title": title, "status": "queued", "step": "차례를 기다리는 중",
            "since": now, "stem": "", "error": "", "segments": 0,
            # 진행 가시성: 어떤 단계인지 · 무엇으로 도는지 · 얼마나 걸릴지
            "phase": "", "phase_since": now, "engine": "", "device": "",
            "diarizer": "", "duration": 0.0, "eta_lo": 0.0, "eta_hi": 0.0,
            "dl_mb": 0.0, "dl_total_mb": 0,
        }
        if len(_JOBS) > _JOBS_KEEP:  # 끝난 것부터 오래된 순으로 정리
            done = [(j["since"], k) for k, j in _JOBS.items()
                    if j["status"] in ("done", "failed")]
            for _, k in sorted(done)[: len(_JOBS) - _JOBS_KEEP]:
                _JOBS.pop(k, None)
    return job_id


def _model_total_mb(model_size: str) -> int:
    from .asr.info import expected_model_mb

    return expected_model_mb(model_size)


def _phase_step(key: str, info: dict) -> str:
    """단계 키 → 대시보드에 보일 문구."""
    return {
        "convert": "오디오 변환 중 (ffmpeg)",
        "model": "모델 여는 중",
        "asr": "전사하는 중 (오디오 → 화자별 텍스트)",
        "diarize": "화자 나누는 중" if info.get("diarizer", "off") != "off" else "정리하는 중",
        "merge": "문장 정리하는 중",
    }.get(key, key)


def _watch_download(job_id: str, repo_id: str, total_mb: int, stop: threading.Event) -> None:
    """모델을 받는 동안 캐시 폴더 크기를 재서 진행률을 보여준다.

    huggingface_hub 이 진행률을 콜백으로 주지 않아 폴더 크기로 갈음한다.
    정확한 수치가 목적이 아니라 **멈춘 게 아니라는 신호**가 목적이다.
    """
    from .asr.info import dir_size_mb, model_cache_path

    path = model_cache_path(repo_id)
    while not stop.wait(2.0):
        mb = dir_size_mb(path)
        _job_set(job_id, dl_mb=round(mb, 1), dl_total_mb=total_mb,
                 step=f"모델 받는 중 · {mb:,.0f} / 약 {total_mb:,}MB (처음 한 번만)")


def run_audio_job(job_id: str, glossary_path: str = "glossary.yaml") -> dict:
    """작업 1건을 **동기로** 수행한다(백그라운드 스레드 / 테스트 공용)."""
    from .asr.info import estimate_range_sec
    from .transcribe import transcribe_audio

    with _JLOCK:
        job = dict(_JOBS[job_id])
    audio = (_data_dir() / job["audio"]).resolve()
    profile = job["profile"]
    dl_stop = threading.Event()
    facts: dict = {}

    def on_phase(key: str, info: dict) -> None:
        if key == "start":
            facts.update(info)
            eta = estimate_range_sec(
                float(info.get("duration") or 0), str(info.get("model") or ""),
                str(info.get("device") or "cpu"),
            ) or (0.0, 0.0)
            _job_set(job_id, engine=info.get("description", ""), device=info.get("device", ""),
                     diarizer=info.get("diarizer", ""), duration=info.get("duration", 0.0),
                     eta_lo=eta[0], eta_hi=eta[1])
            return
        if key == "model" and not facts.get("cached", True):
            total = _model_total_mb(str(facts.get("model") or ""))
            _job_set(job_id, phase=key, phase_since=time.time(),
                     step=f"모델 받는 중 · 약 {total:,}MB (처음 한 번만)", dl_total_mb=total)
            threading.Thread(target=_watch_download, daemon=True,
                             args=(job_id, facts.get("repo_id", ""), total, dl_stop)).start()
            return
        if key == "asr":
            dl_stop.set()  # 다운로드 감시 종료
        _job_set(job_id, phase=key, phase_since=time.time(), step=_phase_step(key, facts))

    try:
        if not _RUN_LOCK.acquire(blocking=False):
            _job_set(job_id, step="앞 회의록이 끝나기를 기다리는 중")
            _RUN_LOCK.acquire()
        try:
            _job_set(job_id, status="running", phase="start", phase_since=time.time(),
                     step="준비하는 중")
            segments = transcribe_audio(audio, glossary_path, on_phase=on_phase)
        finally:
            dl_stop.set()
            _RUN_LOCK.release()

        _job_set(job_id, phase="llm", phase_since=time.time(),
                 step="회의록을 쓰는 중 (LLM)", segments=len(segments))
        glossary = load_glossary(glossary_path)
        meta = {"meeting_title": job["title"], "date": "", "source_audio": audio.name}
        minutes = generate_minutes(
            segments, provider_for_profile(profile), glossary=glossary, meta=meta
        )

        stem = str(_data_dir() / "out" / profile / audio.stem)
        _write(stem, meta, segments, minutes)
        res = _result(stem, segments, minutes)
        _job_set(job_id, status="done", phase="done", step="회의록 완료", stem=stem,
                 minutes_path=_rel(Path(stem + ".minutes.md")))
        return res
    except Exception as e:  # noqa: BLE001  실패도 값으로 남겨 대시보드가 이유를 보여준다
        dl_stop.set()
        _job_set(job_id, status="failed", phase="failed", step="실패", error=str(e))
        return {"ok": False, "error": str(e)}


def start_audio_job(audio: Path, profile: str = "secure", title: str = "") -> str:
    job_id = _job_add(audio, profile, title)
    threading.Thread(target=run_audio_job, args=(job_id,), daemon=True).start()
    return job_id


def ep_audio_process(body: dict) -> dict:
    """이미 data/ 안에 있는 녹음본으로 전사→회의록 작업을 시작한다(재실행 포함)."""
    target = _safe_target(body.get("path") or "")
    if not target.is_file() or not is_audio_name(target.name):
        raise ValueError("녹음본 파일을 찾을 수 없어요")
    job = start_audio_job(target, body.get("profile", "secure"), body.get("title", ""))
    return {"ok": True, "job": job, "path": _rel(target)}


def ep_jobs(_p: dict) -> dict:
    """작업 목록 + 경과 시간(초). 경과는 서버 시계로 계산해 브라우저와 어긋나지 않게 한다."""
    now = time.time()
    with _JLOCK:
        jobs = sorted(_JOBS.values(), key=lambda j: j["since"], reverse=True)
        return {"ok": True, "jobs": [
            {**j, "elapsed": int(now - j["since"]),
             "phase_elapsed": int(now - j.get("phase_since", j["since"]))}
            for j in jobs
        ]}


def upload_audio(name: str, reader, length: int, profile: str = "secure",
                 title: str = "", auto: bool = True, progress: dict | None = None) -> dict:
    """녹음본 저장 + (auto면) 전사·회의록 작업 시작. HTTP 핸들러와 테스트 공용."""
    target = save_audio_stream(name, reader, length, auto=auto, progress=progress)
    res: dict[str, Any] = {"ok": True, "kind": "audio", "path": _rel(target),
                           "name": target.name, "size": target.stat().st_size, "auto": auto}
    if auto:
        res["job"] = start_audio_job(target, profile, title)
    return res


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
                             passcode=passcode, meeting_url=meeting_url,
                             bot_name=body.get("bot_name", ""))
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
    ("GET", "/api/jobs"): ep_jobs,
    ("POST", "/api/upload"): ep_upload,
    ("POST", "/api/audio/process"): ep_audio_process,
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

    def handle_expect_100(self) -> bool:
        """Expect: 100-continue — 본문을 받기 **전에** 상한을 판정해 준다.

        이 헤더를 보내는 클라이언트(curl 등)는 큰 파일을 다 올려보내기 전에
        거절 사유를 정확히 받는다. 브라우저 XHR은 이 헤더를 쓰지 않으므로,
        대시보드는 올리기 전에 자체적으로 크기를 확인한다.
        """
        if urlparse(self.path).path == "/api/upload/audio":
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > _max_upload_bytes("audio"):
                self.close_connection = True
                self._send(400, {"ok": False, "error": str(_too_big("audio"))})
                return False
        return super().handle_expect_100()

    def _drain(self, remaining: int) -> bool:
        """거부 응답을 클라이언트가 읽을 수 있도록 남은 본문을 버린다.

        남은 양이 너무 크면 끝까지 읽는 게 더 낭비라 연결을 끊는다(=True 반환).
        """
        if remaining > _DRAIN_LIMIT:
            return True
        while remaining > 0:
            chunk = self.rfile.read(min(_UPLOAD_CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
        return False

    @staticmethod
    def _header_filename(raw: str) -> str:
        """X-Filename 값을 원래 파일명으로 되돌린다.

        HTTP 헤더는 latin-1로 디코드되므로, URL 인코딩 없이 UTF-8 바이트를 그대로
        보낸 클라이언트의 한글 파일명이 깨진다 — 되살릴 수 있으면 되살린다.
        """
        if not raw:
            return ""
        try:
            raw = raw.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        return unquote(raw)

    def _audio_upload(self) -> None:
        """POST /api/upload/audio — 본문이 JSON이 아니라 **파일 바이트 그대로**."""
        q = parse_qs(urlparse(self.path).query)

        def arg(key: str, default: str = "") -> str:
            return unquote((q.get(key) or [default])[0])

        name = self._header_filename(self.headers.get("X-Filename", "")) or arg("name")
        length = int(self.headers.get("Content-Length", 0) or 0)
        progress = {"read": 0}
        try:
            res = upload_audio(
                name, self.rfile, length,
                profile=arg("profile", "secure"), title=arg("title"),
                auto=arg("auto", "1") not in ("0", "false", "no"),
                progress=progress,
            )
        except Exception as e:  # noqa: BLE001  거부 사유를 JSON으로 돌려준다
            self.close_connection = self._drain(length - progress["read"])
            self._send(400, {"ok": False, "error": str(e)})
            return
        self._send(200, res)

    def do_POST(self) -> None:
        if urlparse(self.path).path == "/api/upload/audio":
            self._audio_upload()
            return
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
