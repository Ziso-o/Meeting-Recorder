"""긴 회의에서 파이프라인이 무너지지 않는지 — 병합 상한·청크 분할·부분 실패 내성.

실제로 겪은 장애를 그대로 재현한다: 화자분리가 꺼진 19분 회의가 세그먼트 1개로
뭉쳐 → 청크 분할 무력화 → LLM 통짜 프롬프트 → 타임아웃 → 전사까지 통째로 유실.
"""

from __future__ import annotations

import io
import time
from itertools import pairwise
from pathlib import Path

import pytest

from minutes import chain, server
from minutes.asr.base import ASRSegment, SpeakerTurn
from minutes.asr.merge import MAX_MERGE_CHARS, MAX_MERGE_GAP, MAX_MERGE_SEC, merge_segments
from minutes.chunk import DEFAULT_MAX_CHARS, chunk_segments
from minutes.schema import Segment

ROOT = Path(__file__).resolve().parent.parent


def _long_meeting(minutes: int = 19) -> list[ASRSegment]:
    """5초짜리 ASR 세그먼트로 이뤄진 긴 회의."""
    n = minutes * 12
    return [ASRSegment(start=i * 5, end=i * 5 + 5, text="회의 발언 내용입니다 " * 3) for i in range(n)]


# ---- 병합 상한 -------------------------------------------------------------

def test_diarizer_off_does_not_collapse_into_one_segment():
    """화자분리가 꺼져 있어도(=모두 같은 화자) 하나로 뭉치면 안 된다."""
    segs = merge_segments(_long_meeting(), [])          # turns=[] → 전부 SPEAKER_00
    assert len(segs) > 10, "회의 전체가 한 세그먼트로 뭉쳤다"
    assert all(len(s.text) <= MAX_MERGE_CHARS for s in segs)
    assert all(s.end - s.start <= MAX_MERGE_SEC + 5 for s in segs)


def test_merge_breaks_on_silence_gap():
    """같은 화자여도 충분히 쉬면 다른 발화로 끊는다."""
    asr = [
        ASRSegment(start=0, end=3, text="첫 발언"),
        ASRSegment(start=3 + MAX_MERGE_GAP / 2, end=8, text="이어지는 말"),   # 짧은 쉼 → 병합
        ASRSegment(start=8 + MAX_MERGE_GAP * 3, end=12, text="한참 뒤 발언"),  # 긴 쉼 → 분리
    ]
    segs = merge_segments(asr, [])
    assert len(segs) == 2
    assert segs[0].text == "첫 발언 이어지는 말"


def test_merge_still_groups_same_speaker():
    """상한을 뒀다고 화자별 묶음이 사라지면 안 된다."""
    asr = [ASRSegment(start=i, end=i + 1, text="말") for i in range(4)]
    turns = [SpeakerTurn(speaker="A", start=0, end=2), SpeakerTurn(speaker="B", start=2, end=4)]
    segs = merge_segments(asr, turns)
    assert [s.speaker for s in segs] == ["A", "B"]


# ---- 청크 분할 -------------------------------------------------------------

def test_oversized_single_segment_is_split():
    """세그먼트 하나가 상한을 넘겨도 청크가 쪼개져야 한다(통짜 프롬프트 방지)."""
    huge = Segment(speaker="SPEAKER_00", start=0, end=1140,
                   text="긴 회의 내용 " * 3000)          # 한 세그먼트에 수만 자
    chunks = chunk_segments([huge])
    assert len(chunks) > 1
    for c in chunks:
        assert sum(len(s.text) for s in c) <= DEFAULT_MAX_CHARS * 1.1
    # 시간 순서와 전체 구간은 보존
    flat = [s for c in chunks for s in c]
    assert flat[0].start == pytest.approx(0, abs=1)
    assert flat[-1].end == pytest.approx(1140, abs=1)
    assert all(a.start <= b.start for a, b in pairwise(flat))


def test_long_meeting_end_to_end_chunking():
    segs = merge_segments(_long_meeting(), [])
    chunks = chunk_segments(segs)
    assert len(chunks) >= 2
    assert all(sum(len(s.text) for s in c) <= DEFAULT_MAX_CHARS * 1.1 for c in chunks)


# ---- 부분 실패 내성 --------------------------------------------------------

class _BoomProvider:
    """용어 교정에서만 터지는 프로바이더(타임아웃 흉내)."""

    name = "boom"

    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str, *, system=None, max_tokens=None) -> str:
        self.calls += 1
        raise TimeoutError("Ollama 응답이 오지 않았어요")


def test_term_correction_failure_is_not_fatal():
    """비치명 단계(용어 교정)가 전체를 죽이면 안 된다 — 원문 유지로 넘어간다."""
    segs = [Segment(speaker="SPEAKER_00", start=0, end=5, text="원문 그대로")]
    out = chain.correct_terms(segs, "", _BoomProvider())
    assert [s.text for s in out] == ["원문 그대로"]


def test_term_correction_can_be_disabled(monkeypatch):
    monkeypatch.setenv("LLM_TERM_CORRECTION", "0")
    assert chain.term_correction_enabled() is False
    p = _BoomProvider()
    segs = [Segment(speaker="SPEAKER_00", start=0, end=5, text="원문")]
    assert chain.correct_terms(segs, "", p) == segs
    assert p.calls == 0                      # LLM 호출 자체가 없어야 한다
    monkeypatch.setenv("LLM_TERM_CORRECTION", "1")
    assert chain.term_correction_enabled() is True


def test_term_correction_is_chunked(monkeypatch):
    """긴 전사를 한 프롬프트에 몰아넣지 않는다."""
    segs = merge_segments(_long_meeting(), [])
    seen: list[int] = []

    class P:
        name = "spy"

        def generate(self, prompt, *, system=None, max_tokens=None):
            seen.append(len(prompt))
            return "[]"   # 개수 불일치 → 원문 유지 경로

    chain.correct_terms(segs, "", P())
    assert len(seen) >= 2, "청크로 나뉘지 않았다"
    assert max(seen) < 40_000


def test_generate_minutes_reports_progress(monkeypatch):
    monkeypatch.setenv("LLM_TERM_CORRECTION", "0")
    from minutes.providers.mock import MockProvider

    segs = merge_segments(_long_meeting(3), [])
    stages: list[tuple[str, int, int]] = []
    chain.generate_minutes(segs, MockProvider(), on_progress=lambda *a: stages.append(a))

    names = [s for s, _, _ in stages]
    assert names.count("summary") >= 1
    assert names.index("terms") < names.index("summary") < names.index("integrate")
    # 요약 단계는 청크마다 1/N, 2/N … 으로 올라간다
    summary = [(d, t) for st, d, t in stages if st == "summary"]
    assert summary[0][0] == 1 and summary[-1][0] == summary[-1][1]
    assert stages[-1] == ("integrate", 1, 1)


# ---- 전사 보존 -------------------------------------------------------------

@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MINUTES_HOME", str(tmp_path))
    monkeypatch.setenv("ASR_ENGINE", "mock")
    monkeypatch.setenv("DIARIZER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.chdir(ROOT)
    (tmp_path / "data").mkdir()
    server._JOBS.clear()
    yield tmp_path
    server._JOBS.clear()


def test_transcript_survives_llm_failure(home, monkeypatch):
    """LLM이 죽어도 오래 걸린 전사는 남아야 한다 — 회의록만 다시 만들 수 있게."""
    monkeypatch.setattr(server, "generate_minutes",
                        lambda *a, **k: (_ for _ in ()).throw(TimeoutError("Ollama 타임아웃")))
    audio = server.save_audio_stream("긴 회의.m4a", io.BytesIO(b"x"), 1)
    job_id = server._job_add(audio, "secure", "")
    res = server.run_audio_job(job_id, glossary_path=str(ROOT / "glossary.yaml"))

    assert res["ok"] is False
    transcript = home / "data" / "out" / "secure" / "긴 회의.transcript.json"
    assert transcript.exists(), "전사가 저장되지 않아 통째로 유실됐다"
    assert "segments" in transcript.read_text(encoding="utf-8")

    job = next(j for j in server.ep_jobs({})["jobs"] if j["id"] == job_id)
    assert job["status"] == "failed" and job["transcript"].endswith(".transcript.json")


def test_job_records_phase_timings(home):
    """끝난 뒤 어느 단계에서 시간이 갔는지 남아야 다음에 뭘 손볼지 알 수 있다."""
    audio = server.save_audio_stream("진행률.m4a", io.BytesIO(b"x"), 1)
    job_id = server._job_add(audio, "secure", "")
    server.run_audio_job(job_id, glossary_path=str(ROOT / "glossary.yaml"))
    job = next(j for j in server.ep_jobs({})["jobs"] if j["id"] == job_id)

    assert job["status"] == "done"
    assert {"asr", "llm"} <= set(job["timings"]), job["timings"]
    assert all(v >= 0 for v in job["timings"].values())
    # 끝난 작업에 낡은 진행바가 남지 않는다
    assert job["prog"] == 0.0 and job["prog_label"] == ""


def test_progress_callback_fills_label_and_remaining(home, monkeypatch):
    import minutes.transcribe as tr

    real = tr.transcribe_audio

    def fake(audio, glossary_path="glossary.yaml", keep_wav=False, on_phase=None, on_progress=None):
        if on_phase:
            on_phase("asr", {})
        if on_progress:
            time.sleep(0.05)          # 처리 속도 실측이 되도록 아주 짧게
            on_progress(300.0, 1200.0)
        return real(audio, glossary_path, keep_wav)

    monkeypatch.setattr(tr, "transcribe_audio", fake)
    audio = server.save_audio_stream("남은시간.m4a", io.BytesIO(b"x"), 1)
    job_id = server._job_add(audio, "secure", "")

    seen: list[dict] = []
    orig = server._job_set

    def spy(jid, **f):
        if f.get("prog_label"):
            seen.append(dict(f))
        orig(jid, **f)

    monkeypatch.setattr(server, "_job_set", spy)
    server.run_audio_job(job_id, glossary_path=str(ROOT / "glossary.yaml"))

    # 전사 진행률(오디오 타임라인 mm:ss)과 회의록 진행률(청크 n/N)이 둘 다 나온다
    asr = next(f for f in seen if ":" in f["prog_label"])
    assert asr["prog"] == pytest.approx(0.25)
    assert asr["prog_label"] == "5:00 / 20:00"
    assert asr["remain"] > 0             # 실측 속도로 남은 시간 추정
    assert any("/" in f["prog_label"] and ":" not in f["prog_label"] for f in seen)


# ---- Ollama 설정 -----------------------------------------------------------
# 스트리밍 동작(폭주 차단·무응답 감지·잘림 경고)은 tests/test_ollama_stream.py 에서
# 실제 HTTP 서버로 검증한다.

def test_ollama_timeout_is_configurable(monkeypatch):
    from minutes.providers.ollama import OllamaProvider

    monkeypatch.delenv("OLLAMA_TIMEOUT", raising=False)
    assert OllamaProvider().timeout == 1800.0
    monkeypatch.setenv("OLLAMA_TIMEOUT", "3600")
    assert OllamaProvider().timeout == 3600.0


# ---- Ollama 컨텍스트 (조용한 잘림 방지) ------------------------------------

def test_context_grows_with_prompt(monkeypatch):
    """기본 num_ctx 를 넘으면 Ollama 가 프롬프트 앞부분을 조용히 버린다 —
    회의 앞부분이 통째로 사라진 요약이 나오는 정확성 버그."""
    from minutes.providers.ollama import OllamaProvider

    monkeypatch.delenv("OLLAMA_MAX_CTX", raising=False)
    p = OllamaProvider()
    assert p.context_size("가" * 500) == 4096
    assert p.context_size("가" * 3000) == 8192
    assert p.context_size("가" * 8743) == 16384          # 실제로 실패했던 크기
    # 상한을 넘지 않는다
    assert p.context_size("가" * 200000) == p.max_ctx


def test_context_cap_is_configurable(monkeypatch):
    from minutes.providers.ollama import OllamaProvider

    monkeypatch.setenv("OLLAMA_MAX_CTX", "8192")
    assert OllamaProvider().context_size("가" * 50000) == 8192


# ---- 청크 크기 · 부분 실패 ---------------------------------------------------

def test_chunk_size_is_configurable(monkeypatch):
    import importlib

    from minutes import chunk as chunk_mod

    monkeypatch.setenv("MINUTES_CHUNK_CHARS", "1200")
    importlib.reload(chunk_mod)
    try:
        assert chunk_mod.DEFAULT_MAX_CHARS == 1200
        segs = merge_segments(_long_meeting(), [])
        for c in chunk_mod.chunk_segments(segs):
            assert sum(len(s.text) for s in c) <= 1200 * 1.1
    finally:
        monkeypatch.delenv("MINUTES_CHUNK_CHARS")
        importlib.reload(chunk_mod)


def test_one_failing_chunk_does_not_kill_the_job():
    """구간 하나가 타임아웃 나도 나머지로 회의록을 만든다."""
    segs = merge_segments(_long_meeting(), [])

    class Flaky:
        name = "flaky"

        def __init__(self):
            self.n = 0

        def generate(self, prompt, *, system=None, max_tokens=None):
            self.n += 1
            if self.n == 2:
                raise TimeoutError("두 번째 구간에서 타임아웃")
            return f"구간 {self.n} 요약함"

    p = Flaky()
    out = chain.summarize_chunks(segs, "", p)
    assert p.n > 2                     # 실패 후에도 계속 진행
    assert len(out) == p.n - 1         # 실패한 하나만 빠짐


def test_all_chunks_failing_raises_real_cause():
    """전부 실패했으면 지어내지 말고 원인을 그대로 올린다."""
    segs = merge_segments(_long_meeting(), [])
    with pytest.raises(RuntimeError, match="모든 구간 요약이 실패"):
        chain.summarize_chunks(segs, "", _BoomProvider())
