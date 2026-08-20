"""진행 가시성 — 단계 구분 · 경과 시간 · 모델 다운로드 표시.

"전사하는 중"만 보여주면 3GB 모델을 받는 중인지 진짜 전사 중인지 알 수 없다.
그 구분에 필요한 정보가 실제로 나오는지 본다.
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path

import pytest

from minutes import server
from minutes.asr import info

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def home(tmp_path, monkeypatch):
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
    monkeypatch.chdir(ROOT)


# ---- 런타임 정보 -----------------------------------------------------------

def test_size_bucket_groups_models():
    assert info.size_bucket("large-v3") == "large"
    assert info.size_bucket("distil-large-v3") == "large"
    assert info.size_bucket("medium") == "medium"
    assert info.size_bucket("small") == "small"
    assert info.size_bucket("tiny") == "tiny"


def test_whisper_repo_id():
    assert info.whisper_repo_id("large-v3") == "Systran/faster-whisper-large-v3"
    # 사용자가 repo 를 직접 준 경우는 그대로
    assert info.whisper_repo_id("myorg/my-whisper") == "myorg/my-whisper"


def test_cache_path_follows_hf_env(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    p = info.model_cache_path("Systran/faster-whisper-large-v3")
    assert p == tmp_path / "hub" / "models--Systran--faster-whisper-large-v3"

    monkeypatch.delenv("HF_HUB_CACHE")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    assert info.model_cache_path("a/b") == tmp_path / "hf" / "hub" / "models--a--b"


def test_is_model_cached(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    repo = "Systran/faster-whisper-large-v3"
    assert info.is_model_cached(repo) is False        # 폴더 자체가 없음

    snap = info.model_cache_path(repo) / "snapshots" / "abc"
    snap.mkdir(parents=True)
    (snap / "model.bin").write_bytes(b"x" * 2_000_000)
    assert info.is_model_cached(repo) is True

    # 받다 만 조각이 있으면 아직 아님
    (info.model_cache_path(repo) / "blobs").mkdir()
    (info.model_cache_path(repo) / "blobs" / "deadbeef.incomplete").write_bytes(b"x")
    assert info.is_model_cached(repo) is False


def test_estimate_range_is_slower_on_cpu():
    cpu = info.estimate_range_sec(1200, "large-v3", "cpu")
    gpu = info.estimate_range_sec(1200, "large-v3", "cuda")
    assert cpu and gpu and cpu[0] > gpu[1]        # CPU 최소 > GPU 최대
    small = info.estimate_range_sec(1200, "small", "cpu")
    assert small and small[1] < cpu[1]            # 작은 모델이 더 빠름
    assert info.estimate_range_sec(0, "large-v3", "cpu") is None


def test_describe_engine_shows_model_and_device(monkeypatch):
    monkeypatch.setattr(info, "asr_device", lambda: "cuda")
    from minutes.asr.whisper_engine import FasterWhisperEngine

    assert info.describe_engine(FasterWhisperEngine(model_size="large-v3")) == \
        "faster-whisper large-v3 · CUDA"

    from minutes.asr.mock import MockASREngine

    assert info.describe_engine(MockASREngine()) == "mock"


# ---- 단계 콜백 -------------------------------------------------------------

def test_transcribe_reports_phases_in_order(tmp_path, mock_engines):
    from minutes.transcribe import transcribe_audio

    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"fake")
    seen: list[tuple[str, dict]] = []
    transcribe_audio(audio, str(ROOT / "glossary.yaml"), on_phase=lambda k, i: seen.append((k, i)))

    keys = [k for k, _ in seen]
    assert keys == ["start", "model", "asr", "diarize", "merge"]   # mock 은 ffmpeg 변환 생략
    start = dict(seen[0][1])
    assert start["engine"] == "mock" and start["diarizer"] == "mock"


def test_model_load_is_separate_from_transcribe():
    """다운로드 단계를 따로 보여주려면 load() 가 transcribe 와 분리돼 있어야 한다."""
    from minutes.asr.whisper_engine import FasterWhisperEngine

    assert callable(FasterWhisperEngine(model_size="tiny").load)
    from minutes.asr.mock import MockASREngine

    assert MockASREngine().load() is None


# ---- 작업 진행 상황 --------------------------------------------------------

def test_job_records_engine_duration_and_eta(home, mock_engines, monkeypatch):
    import minutes.transcribe as tr

    real = tr.transcribe_audio

    def fake(audio, glossary_path="glossary.yaml", keep_wav=False, on_phase=None):
        # 실제 large-v3/CPU 상황을 흉내내 job 에 무엇이 남는지 본다
        if on_phase:
            on_phase("start", {"engine": "faster-whisper", "model": "large-v3",
                               "device": "cpu", "diarizer": "off", "duration": 1200.0,
                               "description": "faster-whisper large-v3 · CPU",
                               "repo_id": "Systran/faster-whisper-large-v3", "cached": True})
            on_phase("asr", {})
        return real(audio, glossary_path, keep_wav)

    monkeypatch.setattr(tr, "transcribe_audio", fake)
    audio = server.save_audio_stream("긴회의.m4a", io.BytesIO(b"x"), 1)
    job_id = server._job_add(audio, "secure", "")
    server.run_audio_job(job_id, glossary_path=str(ROOT / "glossary.yaml"))

    job = next(j for j in server.ep_jobs({})["jobs"] if j["id"] == job_id)
    assert job["engine"] == "faster-whisper large-v3 · CPU"
    assert job["device"] == "cpu" and job["diarizer"] == "off"
    assert job["duration"] == 1200.0
    assert job["eta_lo"] > 0 and job["eta_hi"] > job["eta_lo"]   # 20분 녹음 · CPU → 범위 존재


def test_jobs_expose_elapsed(home, mock_engines):
    audio = server.save_audio_stream("경과.m4a", io.BytesIO(b"x"), 1)
    job_id = server._job_add(audio, "secure", "")
    server._JOBS[job_id]["since"] = time.time() - 125
    server._JOBS[job_id]["phase_since"] = time.time() - 40

    job = server.ep_jobs({})["jobs"][0]
    assert 120 <= job["elapsed"] <= 130         # 서버가 계산(브라우저 시계 무관)
    assert 35 <= job["phase_elapsed"] <= 45     # 현재 단계 경과는 따로


def test_download_watcher_reports_growing_size(home, tmp_path, monkeypatch):
    """'멈춘 게 아니라 받는 중'이 숫자로 보여야 한다."""
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    repo = "Systran/faster-whisper-large-v3"
    blobs = info.model_cache_path(repo) / "blobs"
    blobs.mkdir(parents=True)
    (blobs / "part.incomplete").write_bytes(b"x" * (7 * 1024 * 1024))

    audio = server.save_audio_stream("받는중.m4a", io.BytesIO(b"x"), 1)
    job_id = server._job_add(audio, "secure", "")
    stop = threading.Event()
    t = threading.Thread(target=server._watch_download, args=(job_id, repo, 3090, stop))
    t.start()
    try:
        deadline = time.time() + 10
        while time.time() < deadline and not server._JOBS[job_id]["dl_mb"]:
            time.sleep(0.05)
    finally:
        stop.set()
        t.join(5)

    job = server._JOBS[job_id]
    assert job["dl_mb"] == pytest.approx(7, abs=1)
    assert job["dl_total_mb"] == 3090
    assert "모델 받는 중" in job["step"] and "3,090MB" in job["step"]


def test_phase_labels_reflect_diarizer_off():
    assert "화자" in server._phase_step("diarize", {"diarizer": "pyannote"})
    assert "화자" not in server._phase_step("diarize", {"diarizer": "off"})
    assert server._phase_step("asr", {}) == "전사하는 중 (오디오 → 화자별 텍스트)"


# ---- 대시보드 --------------------------------------------------------------

def test_dashboard_renders_progress_details():
    html = server.INDEX_HTML
    assert "fmtDur" in html and "phase_elapsed" in html   # 경과 시간
    assert "dlBar" in html and "dl_total_mb" in html      # 다운로드 진행바
    assert "jobWhy" in html and "전사 예상" in html         # 엔진·디바이스·예상 시간
