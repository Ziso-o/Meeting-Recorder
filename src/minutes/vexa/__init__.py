"""Vexa 봇 연동 서브패키지 (Phase 4).

- VexaClient   : 실제 Vexa REST API
- MockVexaClient: 오프라인/테스트
- vexa_to_segments: Vexa 전사 → Phase 1 입력 스키마

환경변수:
  VEXA_API_URL, VEXA_API_KEY, VEXA_BOT_NAME(봇 표시명), VEXA_CLIENT=mock(테스트)
"""

from __future__ import annotations

import os

from .convert import vexa_to_segments

__all__ = ["vexa_to_segments", "select_vexa_client"]


def select_vexa_client():
    """환경변수에 따라 Vexa 클라이언트를 생성한다. VEXA_CLIENT=mock이면 목."""
    bot_name = os.environ.get("VEXA_BOT_NAME", "회의록봇")

    if os.environ.get("VEXA_CLIENT", "").lower() == "mock":
        from .mock import MockVexaClient

        return MockVexaClient(bot_name=bot_name)

    from .client import VexaClient

    return VexaClient(
        base_url=os.environ.get("VEXA_API_URL", ""),
        api_key=os.environ.get("VEXA_API_KEY", ""),
        bot_name=bot_name,
    )
