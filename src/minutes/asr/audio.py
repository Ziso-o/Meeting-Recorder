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
