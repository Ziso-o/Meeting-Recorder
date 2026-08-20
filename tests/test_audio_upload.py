"""녹음본(클로바 노트 m4a 등) 업로드 → 전사 → 회의록 자동 생성 경로 테스트.

네트워크·GPU·ffmpeg 없이 mock 엔진으로 e2e 확인한다.
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path

import pytest

from minutes import server
from minutes.audio_formats import AUDIO_EXTS, audio_ext, is_audio_name

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def home(tmp_path, monkeypatch):
    """MINUTES_HOME 을 임시폴더로 돌리고 작업 기록을 비운다."""
    monkeypatch.setenv("MINUTES_HOME", str(tmp_path))
    (tmp_path / "data").mkdir()
    server._JOBS.clear()
    yield tmp_path
    server._JOBS.clear()


@pytest.fixture
def mock_engines(monkeypatch):
    monkeypatch.setenv("ASR_ENGINE", "mock")
    monkeypatch.setenv("DIARIZER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.chdir(ROOT)  # glossary.yaml 상대경로


# ---- 형식 판별 -------------------------------------------------------------

def test_clova_m4a_is_supported():
    # 클로바 노트가 내보내는 기본 형식
    assert is_audio_name("2026-08-20 회의.m4a")
    assert audio_ext("REC.M4A") == ".m4a"
    for ext in (".aac", ".mp3", ".wav", ".flac", ".ogg"):
        assert ext in AUDIO_EXTS


def test_unsupported_format_rejected():
    with pytest.raises(ValueError, match="지원하지 않는"):
        audio_ext("회의록.txt")
    with pytest.raises(ValueError):
        audio_ext("확장자없음")


# ---- 저장(스트리밍) --------------------------------------------------------

def test_save_audio_stream_writes_original_extension(home):
    data = b"\x00\x01fake-m4a" * 100
    target = server.save_audio_stream("개발 회의.m4a", io.BytesIO(data), len(data))
    assert target.suffix == ".m4a"
    assert target.read_bytes() == data
    assert target.parent == home / "data" / "uploads" / "audio"
    assert not list(target.parent.glob("*.part"))  # 임시파일 잔여 없음


def test_save_audio_stream_no_overwrite(home):
    for _ in range(2):
        server.save_audio_stream("같은이름.m4a", io.BytesIO(b"xx"), 2)
    names = sorted(p.name for p in (home / "data" / "uploads" / "audio").iterdir())
    assert names == ["같은이름(1).m4a", "같은이름.m4a"]


def test_manual_mode_lands_in_incoming(home):
    """auto=False 면 외부 minutes.watch 가 집어가도록 data/incoming 에 둔다."""
    res = server.upload_audio("회의.m4a", io.BytesIO(b"abc"), 3, auto=False)
    assert res["path"].startswith("incoming/")
    assert "job" not in res
    assert (home / "data" / "incoming" / "회의.m4a").exists()


def test_path_traversal_in_filename_neutralized(home):
    target = server.save_audio_stream("../../etc/passwd.m4a", io.BytesIO(b"x"), 1)
    assert target.parent == home / "data" / "uploads" / "audio"
    assert "/" not in target.name and ".." not in target.stem


# ---- 크기 상한 -------------------------------------------------------------

def test_audio_limit_is_configurable(home, monkeypatch):
    monkeypatch.setenv("MINUTES_MAX_UPLOAD_MB", "500")
    assert server._max_upload_bytes("audio") == 500 * 1024 * 1024
    monkeypatch.setenv("MINUTES_MAX_UPLOAD_MB", "1")
    with pytest.raises(ValueError, match="너무 큽니다"):
        server.save_audio_stream("큰파일.m4a", io.BytesIO(b"x"), 2 * 1024 * 1024)
    # 상한 이하는 통과
    small = b"y" * 1024
    assert server.save_audio_stream("작은파일.m4a", io.BytesIO(small), len(small)).exists()


def test_audio_default_limit_is_500mb(home, monkeypatch):
    monkeypatch.delenv("MINUTES_MAX_UPLOAD_MB", raising=False)
    assert server._max_upload_bytes("audio") == 500 * 1024 * 1024


def test_text_limit_counts_bytes_not_characters(home, monkeypatch):
    """한글은 UTF-8에서 3바이트 — 예전엔 문자 수로 세어 상한이 3배로 헐거웠다."""
    monkeypatch.setenv("MINUTES_MAX_TEXT_UPLOAD_MB", "1")
    limit = server._max_upload_bytes("text")
    assert limit == 1024 * 1024
    korean = "가" * (limit // 3 + 10)          # 문자 수는 상한 미만, 바이트는 초과
    assert len(korean) < limit < len(korean.encode("utf-8"))
    with pytest.raises(ValueError, match="너무 큽니다"):
        server.ep_upload({"kind": "minutes", "name": "큰회의록.md", "content": korean})


def test_oversized_upload_leaves_no_partial_file(home, monkeypatch):
    monkeypatch.setenv("MINUTES_MAX_UPLOAD_MB", "1")
    with pytest.raises(ValueError):
        server.save_audio_stream("큰파일.m4a", io.BytesIO(b"x" * 10), 99 * 1024 * 1024)
    assert not (home / "data" / "uploads" / "audio").exists() or \
        not list((home / "data" / "uploads" / "audio").iterdir())


def test_truncated_upload_is_rejected(home):
    """Content-Length 보다 적게 들어오면 반쪽 파일을 남기지 않는다."""
    with pytest.raises(ValueError, match="끊겼"):
        server.save_audio_stream("끊긴파일.m4a", io.BytesIO(b"ab"), 100)
    assert not list((home / "data" / "uploads" / "audio").glob("*"))


def test_json_upload_endpoint_points_to_audio_endpoint(home):
    with pytest.raises(ValueError, match="/api/upload/audio"):
        server.ep_upload({"kind": "audio", "name": "회의.m4a", "content": "..."})


# ---- 전사→회의록 작업 -------------------------------------------------------

def test_job_produces_minutes(home, mock_engines):
    audio = server.save_audio_stream("정기 회의.m4a", io.BytesIO(b"fake"), 4)
    job_id = server._job_add(audio, "secure", "정기 회의")
    res = server.run_audio_job(job_id, glossary_path=str(ROOT / "glossary.yaml"))

    assert res["ok"] is True
    assert Path(res["minutes_md"]).exists()
    assert (home / "data" / "out" / "secure" / "정기 회의.transcript.json").exists()

    job = next(j for j in server.ep_jobs({})["jobs"] if j["id"] == job_id)
    assert job["status"] == "done" and job["segments"] >= 1


def test_job_records_failure_reason(home, monkeypatch):
    monkeypatch.setenv("ASR_ENGINE", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    audio = server.save_audio_stream("실패.m4a", io.BytesIO(b"fake"), 4)
    job_id = server._job_add(audio, "secure", "")
    monkeypatch.setattr(
        server, "generate_minutes",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("LLM 연결 실패")),
    )
    res = server.run_audio_job(job_id, glossary_path=str(ROOT / "glossary.yaml"))

    assert res["ok"] is False
    job = server.ep_jobs({})["jobs"][0]
    assert job["status"] == "failed" and "LLM 연결 실패" in job["error"]


def test_upload_audio_auto_runs_in_background(home, mock_engines):
    data = b"fake-audio"
    res = server.upload_audio("자동 회의.m4a", io.BytesIO(data), len(data),
                              profile="secure", title="자동 회의")
    assert res["ok"] is True and res["job"]

    deadline = time.time() + 20
    while time.time() < deadline:
        job = next(j for j in server.ep_jobs({})["jobs"] if j["id"] == res["job"])
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert job["status"] == "done", job.get("error")
    assert (home / "data" / "out" / "secure" / "자동 회의.minutes.md").exists()


def test_reprocess_existing_audio(home, mock_engines):
    """data/incoming 에 직접 넣은 파일도 대시보드에서 처리할 수 있다."""
    inc = home / "data" / "incoming"
    inc.mkdir(parents=True)
    (inc / "손으로넣은.m4a").write_bytes(b"fake")
    res = server.ep_audio_process({"path": "incoming/손으로넣은.m4a", "profile": "secure"})
    assert res["ok"] is True and res["job"]


def test_reprocess_rejects_non_audio_and_traversal(home):
    (home / "data" / "note.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        server.ep_audio_process({"path": "note.txt"})
    with pytest.raises(ValueError, match="허용되지 않은"):
        server.ep_audio_process({"path": "../../etc/passwd.m4a"})


# ---- 파일 목록/관리 --------------------------------------------------------

def test_audio_appears_in_file_list(home):
    server.save_audio_stream("목록 회의.m4a", io.BytesIO(b"x"), 1)
    files = server.ep_files({})["files"]
    assert [f["kind"] for f in files] == ["audio"]
    assert files[0]["name"] == "목록 회의.m4a"


def test_audio_preview_gives_clear_message(home):
    server.save_audio_stream("미리보기.m4a", io.BytesIO(b"x"), 1)
    with pytest.raises(ValueError, match="글로 볼 수 없어요"):
        server.ep_file({"path": "uploads/audio/미리보기.m4a"})


def test_rename_audio_keeps_extension(home):
    server.save_audio_stream("옛이름.m4a", io.BytesIO(b"x"), 1)
    res = server.ep_rename({"path": "uploads/audio/옛이름.m4a", "name": "새 이름"})
    assert res["path"].endswith("새 이름.m4a")
    assert (home / "data" / "uploads" / "audio" / "새 이름.m4a").exists()


def test_delete_audio(home):
    server.save_audio_stream("지울것.m4a", io.BytesIO(b"x"), 1)
    assert server.ep_delete({"path": "uploads/audio/지울것.m4a"})["ok"] is True
    assert server.ep_files({})["files"] == []


def test_health_reports_upload_limits(monkeypatch):
    monkeypatch.setenv("MINUTES_MAX_UPLOAD_MB", "300")
    limits = server.ep_health({})["limits"]
    assert limits["audio_mb"] == 300 and limits["text_mb"] >= 1


# ---- 대시보드 --------------------------------------------------------------

def test_dashboard_has_audio_upload():
    html = server.INDEX_HTML
    assert "/api/upload/audio" in html
    assert ".m4a" in html and ".aac" in html      # 파일 선택창에 클로바 형식 노출
    assert "녹음본 올리기" in html                  # 내비게이션
    assert "uploadAudio" in html and "loadJobs" in html


def test_jobs_run_one_at_a_time(home, mock_engines):
    """전사는 GPU·메모리를 크게 쓴다 — 동시에 두 건이 겹치면 안 된다."""
    import minutes.transcribe as tr

    overlap, live = [], []
    real = tr.transcribe_audio

    def slow(*a, **k):
        live.append(1)
        overlap.append(len(live))
        time.sleep(0.15)
        live.pop()
        return real(*a, **k)

    tr.transcribe_audio = slow  # run_audio_job 이 지연 임포트하므로 모듈 쪽을 갈아끼운다
    try:
        ids = []
        for i in range(3):
            audio = server.save_audio_stream(f"동시{i}.m4a", io.BytesIO(b"x"), 1)
            ids.append(server._job_add(audio, "secure", ""))
        threads = [threading.Thread(target=server.run_audio_job, args=(j,),
                                    kwargs={"glossary_path": str(ROOT / "glossary.yaml")})
                   for j in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
    finally:
        tr.transcribe_audio = real

    assert max(overlap) == 1, f"전사가 겹쳐서 실행됨: {overlap}"
    assert all(j["status"] == "done" for j in server.ep_jobs({})["jobs"])
