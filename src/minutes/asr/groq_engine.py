"""GroqEngine — 클라우드 전사 폴백 (whisper-large-v3-turbo).

GPU가 없을 때 사용. Groq는 OpenAI 호환 audio/transcriptions 엔드포인트를 제공한다.
API 키는 .env(GROQ_API_KEY)에서만. httpx는 지연 임포트.

⚠️ 오디오가 클라우드로 전송된다 — B2G 민감 회의에는 로컬(faster-whisper)을 쓸 것.
"""

from __future__ import annotations

from pathlib import Path

from .base import ASRSegment

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqEngine:
    name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str = "whisper-large-v3-turbo",
        language: str = "ko",
        timeout: float = 300.0,
    ) -> None:
        if not api_key:
            raise ValueError("GROQ_API_KEY가 없습니다. .env를 확인하세요.")
        self.api_key = api_key
        self.model = model
        self.language = language
        self.timeout = timeout

    def load(self) -> None:
        return None  # 클라우드 API — 받아 둘 모델이 없다

    def transcribe(self, wav_path: str, initial_prompt: str = "") -> list[ASRSegment]:
        import httpx  # 지연 임포트

        with Path(wav_path).open("rb") as f:
            files = {"file": (Path(wav_path).name, f, "audio/wav")}
            data = {
                "model": self.model,
                "language": self.language,
                "response_format": "verbose_json",
                "prompt": initial_prompt,
            }
            resp = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=data,
                files=files,
                timeout=self.timeout,
            )
        resp.raise_for_status()
        payload = resp.json()
        segs = payload.get("segments") or []
        if segs:
            return [
                ASRSegment(
                    start=float(s["start"]), end=float(s["end"]), text=s["text"].strip()
                )
                for s in segs
            ]
        # 세그먼트가 없으면 전체 텍스트를 단일 세그먼트로.
        text = payload.get("text", "").strip()
        return [ASRSegment(start=0.0, end=0.0, text=text)] if text else []
