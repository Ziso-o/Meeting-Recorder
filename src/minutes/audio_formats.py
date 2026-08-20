"""오디오 파일 형식 판별 — 업로드(server)·폴더감시(watch) 공용.

무거운 의존성(asr/pipeline)을 끌어오지 않도록 **표준 라이브러리만** 쓴다.
실제 디코딩은 ffmpeg가 하므로(`asr/audio.py`), 여기 목록은 "받아줄 확장자"의
화이트리스트일 뿐이다. 클로바 노트는 보통 `.m4a`(AAC)로 내보낸다.
"""

from __future__ import annotations

from pathlib import Path

AUDIO_EXTS = frozenset({
    ".m4a", ".aac", ".mp3", ".wav", ".flac", ".ogg", ".oga", ".opus",
    ".webm", ".mp4", ".amr", ".wma",
})

#: <input type="file" accept="..."> 에 그대로 넣는 문자열
ACCEPT_ATTR = ",".join(sorted(AUDIO_EXTS))


def is_audio_name(name: str) -> bool:
    """파일명(경로 아님)이 지원 오디오 확장자인지."""
    return Path(name).suffix.lower() in AUDIO_EXTS


def audio_ext(name: str) -> str:
    """지원 오디오 확장자를 소문자로 반환. 아니면 ValueError."""
    ext = Path(name).suffix.lower()
    if ext not in AUDIO_EXTS:
        raise ValueError(
            f"지원하지 않는 오디오 형식입니다: {ext or '(확장자 없음)'} "
            f"— {', '.join(sorted(AUDIO_EXTS))} 중 하나여야 해요."
        )
    return ext
