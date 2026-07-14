"""VexaClient — Vexa(셀프호스팅) REST API 클라이언트.

Vexa 봇을 회의에 dispatch하고, 내장 전사를 가져오고, 봇을 종료한다.
API 키는 .env(VEXA_API_KEY)에서만. 봇 표시명은 config(VEXA_BOT_NAME)에서 지정.
httpx는 지연 임포트.

참고 엔드포인트 (Vexa 공개 API):
  POST   /bots                                   봇 참석 요청
  GET    /transcripts/{platform}/{meeting_id}    전사 조회
  DELETE /bots/{platform}/{meeting_id}           봇 종료
  GET    /bots/status                            봇 상태
"""

from __future__ import annotations

from typing import Any


class VexaClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        bot_name: str = "회의록봇",
        timeout: float = 30.0,
    ) -> None:
        if not base_url:
            raise ValueError("VEXA_API_URL이 없습니다. .env를 확인하세요.")
        if not api_key:
            raise ValueError("VEXA_API_KEY가 없습니다. .env를 확인하세요.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.bot_name = bot_name
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    def _client(self):
        import httpx  # 지연 임포트

        return httpx.Client(base_url=self.base_url, headers=self._headers(), timeout=self.timeout)

    def request_bot(
        self,
        platform: str,
        native_meeting_id: str,
        language: str = "ko",
        task: str = "transcribe",
    ) -> dict[str, Any]:
        """봇을 회의에 참석시킨다."""
        body = {
            "platform": platform,
            "native_meeting_id": native_meeting_id,
            "bot_name": self.bot_name,
            "language": language,
            "task": task,
        }
        with self._client() as c:
            r = c.post("/bots", json=body)
            r.raise_for_status()
            return r.json()

    def get_transcript(self, platform: str, native_meeting_id: str) -> dict[str, Any]:
        """Vexa 내장 전사를 조회한다."""
        with self._client() as c:
            r = c.get(f"/transcripts/{platform}/{native_meeting_id}")
            r.raise_for_status()
            return r.json()

    def stop_bot(self, platform: str, native_meeting_id: str) -> dict[str, Any]:
        """봇을 회의에서 내보낸다."""
        with self._client() as c:
            r = c.delete(f"/bots/{platform}/{native_meeting_id}")
            r.raise_for_status()
            return r.json() if r.content else {"status": "stopped"}

    def bot_status(self) -> dict[str, Any]:
        with self._client() as c:
            r = c.get("/bots/status")
            r.raise_for_status()
            return r.json()
