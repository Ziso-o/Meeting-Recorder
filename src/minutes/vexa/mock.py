"""MockVexaClient — 오프라인/테스트용. 네트워크 없이 Vexa 응답을 흉내낸다."""

from __future__ import annotations

from typing import Any


class MockVexaClient:
    def __init__(self, bot_name: str = "회의록봇") -> None:
        self.bot_name = bot_name
        self.dispatched: list[tuple[str, str]] = []
        self.stopped: list[tuple[str, str]] = []

    def request_bot(
        self, platform: str, native_meeting_id: str, language: str = "ko",
        task: str = "transcribe", passcode: str = "", meeting_url: str = "",
    ) -> dict[str, Any]:
        self.dispatched.append((platform, native_meeting_id))
        return {
            "status": "requested",
            "bot_name": self.bot_name,
            "platform": platform,
            "native_meeting_id": native_meeting_id,
        }

    def get_transcript(self, platform: str, native_meeting_id: str) -> dict[str, Any]:
        return {
            "platform": platform,
            "native_meeting_id": native_meeting_id,
            "segments": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 3.0, "text": "회의 시작하겠습니다"},
                {"speaker": "SPEAKER_01", "start": 3.0, "end": 6.0, "text": "네 자료 공유드립니다"},
                {"speaker": "SPEAKER_00", "start": 6.0, "end": 9.0, "text": "다음 주까지 정리하겠습니다"},
            ],
        }

    def stop_bot(self, platform: str, native_meeting_id: str) -> dict[str, Any]:
        self.stopped.append((platform, native_meeting_id))
        return {"status": "stopped"}

    def bot_status(self) -> dict[str, Any]:
        return {"running_bots": []}
