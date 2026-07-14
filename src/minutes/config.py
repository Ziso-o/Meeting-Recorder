"""설정 및 보안 프로파일.

보안등급 분기 (B2G 공공사업):
- profile="secure"   → 로컬 LLM(Ollama). 민감 회의. 회의 내용이 외부로 나가지 않는다.
- profile="internal" → 클라우드 LLM(Gemini 무료티어). 내부 회의.

API 키/호스트/모델은 .env(또는 환경변수)에서만 읽는다. 코드 하드코딩 금지.
"""

from __future__ import annotations

import os
from pathlib import Path

from .providers import GeminiProvider, LLMProvider, MockProvider, OllamaProvider

PROFILES = ("internal", "secure")


def load_dotenv(path: str | Path = ".env") -> None:
    """의존성 없이 .env를 환경변수로 로드한다(이미 설정된 값은 덮어쓰지 않음)."""
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def provider_for_profile(profile: str) -> LLMProvider:
    """보안 프로파일에 맞는 LLM 프로바이더를 생성한다.

    LLM_PROVIDER 환경변수가 있으면 프로파일 기본값을 덮어쓴다(운영 유연성).
    """
    if profile not in PROFILES:
        raise ValueError(f"알 수 없는 프로파일: {profile!r} (허용: {PROFILES})")

    default = "ollama" if profile == "secure" else "gemini"
    provider = os.environ.get("LLM_PROVIDER", default).lower()

    if provider == "ollama":
        return OllamaProvider(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "qwen2.5:14b"),
        )
    if provider == "gemini":
        return GeminiProvider(
            api_key=os.environ.get("GEMINI_API_KEY", ""),
            model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        )
    if provider == "mock":
        # 오프라인/스모크 테스트용. LLM_PROVIDER=mock 일 때만 선택됨.
        return MockProvider()
    raise ValueError(f"지원하지 않는 LLM_PROVIDER: {provider!r}")
