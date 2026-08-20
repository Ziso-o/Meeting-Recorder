"""오디오 전처리 — ffmpeg로 16kHz mono wav 변환.

faster-whisper / pyannote 모두 16kHz mono PCM을 기대한다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg가 설치되어 있지 않습니다. (apt install ffmpeg 등)")


def probe_duration_sec(input_path: str | Path) -> float:
    """오디오 길이(초). ffprobe가 없거나 읽지 못하면 0.0.

    예상 소요시간 안내에만 쓰므로 실패해도 파이프라인을 막지 않는다.
    """
    if shutil.which("ffprobe") is None:
        return 0.0
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(input_path)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        return max(0.0, float(out.stdout.strip()))
    except (subprocess.SubprocessError, ValueError, OSError):
        return 0.0


def to_wav_16k_mono(input_path: str | Path, out_path: str | Path | None = None) -> Path:
    """임의 오디오(m4a/mp3/...)를 16kHz mono wav로 변환하고 경로를 반환한다."""
    ensure_ffmpeg()
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"오디오 파일이 없습니다: {src}")

    dst = Path(out_path) if out_path else src.with_suffix(".16k.wav")
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-ac", "1", "-ar", "16000", "-vn",
        "-f", "wav", str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dst
