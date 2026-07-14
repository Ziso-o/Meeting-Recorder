"""LLM 프로바이더 어댑터.

STUB — Phase 1에서 구현한다.

어댑터 패턴:
    - OllamaProvider  (로컬, 민감 회의 / profile=secure)
    - GeminiProvider  (클라우드 무료티어, 내부 회의 / profile=internal)

config로 전환 가능하게 공통 인터페이스(예: generate(prompt) -> str)를 정의한다.
"""
