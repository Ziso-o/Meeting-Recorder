"""Phase 1 — 회의록 생성기 CLI (텍스트 → 회의록).

STUB — Phase 1에서 구현한다. 앞서가지 마라.

목표 인터페이스:
    python -m minutes.generate --input transcript.json --profile internal|secure

3단 LLM 체인 (Phase 1에서 구현):
    1. 용어 교정 (glossary.yaml 주입)
    2. 청크 요약 (30분/토큰 한계 단위)
    3. 통합 회의록 (pydantic 스키마 검증, 실패 시 1회 재시도)
"""


def main() -> None:
    raise NotImplementedError("Phase 1에서 구현 예정")


if __name__ == "__main__":
    main()
