"""설정 및 보안 프로파일.

보안등급 분기 (B2G 공공사업):
- profile="secure"   → 로컬 LLM(Ollama). 민감 회의. 회의 내용이 외부로 나가지 않는다.
- profile="internal" → 기본 Gemini(클라우드). 단, 키가 없으면 로컬 Ollama로 폴백(무료·로컬).

API 키/호스트/모델은 .env(또는 환경변수)에서만 읽는다. 코드 하드코딩 금지.
"""

from __future__ import annotations

import os
import sys
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

    무료·로컬 정책: `internal` 기본은 Gemini(클라우드)지만, GEMINI_API_KEY가 없으면
    크래시 대신 **로컬 Ollama로 폴백**(경고 출력)한다. 키가 있으면 종전대로 Gemini.
    (secure는 항상 로컬 Ollama.)
    """
    if profile not in PROFILES:
        raise ValueError(f"알 수 없는 프로파일: {profile!r} (허용: {PROFILES})")

    explicit = os.environ.get("LLM_PROVIDER")
    if explicit:
        provider = explicit.lower()
    else:
        provider = "ollama" if profile == "secure" else "gemini"
        if provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
            print(
                "경고: GEMINI_API_KEY가 없어 로컬 Ollama로 폴백합니다(무료·로컬). "
                "Gemini(클라우드)를 쓰려면 GEMINI_API_KEY를 설정하세요.",
                file=sys.stderr,
            )
            provider = "ollama"

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
