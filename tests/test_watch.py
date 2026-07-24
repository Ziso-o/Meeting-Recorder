"""watch(폴더 감시) + .env 인라인 주석 파서 테스트."""

from __future__ import annotations

from pathlib import Path

from minutes import watch
from minutes.config import _parse_env_value


# ---- .env 인라인 주석 함정 (SESSION_HANDOFF) ----
def test_env_inline_comment_stripped():
    assert _parse_env_value("qwen2.5:7b        # CPU/저사양") == "qwen2.5:7b"
    assert _parse_env_value("faster-whisper  # auto도 이걸로") == "faster-whisper"


def test_env_plain_and_quoted():
    assert _parse_env_value("http://localhost:11434") == "http://localhost:11434"
    assert _parse_env_value('"a # b"') == "a # b"       # 따옴표 안 #는 보존
    assert _parse_env_value("hf_abc#nospace") == "hf_abc#nospace"  # 공백 없는 #는 보존


# ---- watch 처리 로직 ----
def test_run_once_requires_stable_size(tmp_path, monkeypatch):
    monkeypatch.setenv("ASR_ENGINE", "mock")
    monkeypatch.setenv("DIARIZER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    incoming = tmp_path / "incoming"
    out_dir = tmp_path / "out"
    done_dir = tmp_path / "done"
    failed_dir = tmp_path / "failed"
    incoming.mkdir()
    glossary = str(Path(__file__).resolve().parent.parent / "glossary.yaml")

    audio = incoming / "secure_mtg.m4a"
    audio.write_bytes(b"")

    size_cache: dict[str, int] = {}
    common = dict(
        incoming=incoming, out_dir=out_dir, done_dir=done_dir, failed_dir=failed_dir,
        profile="secure", glossary=glossary, size_cache=size_cache,
    )

    # 1차 스캔: 크기 기록만(안정 전) → 처리 안 함
    assert watch.run_once(**common) == []
    assert audio.exists()

    # 2차 스캔: 크기 안정 → 처리 → done 이동 + 회의록 생성
    processed = watch.run_once(**common)
    assert audio in processed
    assert not audio.exists()                       # incoming에서 사라짐
    assert (done_dir / "secure_mtg.m4a").exists()   # done 으로 이동
    assert (out_dir / "secure_mtg.minutes.md").exists()
    assert (out_dir / "secure_mtg.transcript.json").exists()


def test_find_audio_filters_non_audio(tmp_path):
    d = tmp_path / "in"
    d.mkdir()
    (d / "a.m4a").write_bytes(b"")
    (d / "b.txt").write_text("x")
    (d / "c.WAV").write_bytes(b"")  # 대문자 확장자
    found = {p.name for p in watch.find_audio(d)}
    assert found == {"a.m4a", "c.WAV"}
