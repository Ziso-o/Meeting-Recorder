"""로컬 LLM 속도 측정 — 파이프라인 전체를 돌리지 않고 tok/s 만 빠르게 본다.

    python scripts/bench_llm.py                 # 현재 .env 설정으로 1회
    python scripts/bench_llm.py --threads 0,4,8,12   # 스레드 수를 바꿔가며 비교
    python scripts/bench_llm.py --model qwen2.5:3b,qwen2.5:7b

회의록 한 건은 15분 넘게 걸려 설정을 바꿔가며 시험할 수가 없다. 여기서는
짧은 생성 한 번(수십 초)으로 같은 판단을 한다.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

#: 실제 구간 요약과 비슷한 모양의 짧은 작업(입력 길이는 짧게, 출력은 고정).
PROMPT = """다음 회의 발언을 개조식(명사형 종결·마침표 없음)으로 5줄 요약하라.

[SPEAKER_00] 이번 AIOT 사업 자료는 기현 수석하고 전략계획실이 같이 작성하기로 했고요
[SPEAKER_00] TTA 협업 일정 때문에 8월 초까지는 초안이 나와야 합니다
[SPEAKER_00] 실증 구역은 일단 부산시 전체로 잡고 가겠습니다
[SPEAKER_00] 예산은 1.5억 규모로 보고 있는데 확정은 다음 주에 하시죠
[SPEAKER_00] 그리고 지난번에 얘기 나온 온나라 연동은 아직 결론이 안 났습니다
"""


def bench(model: str, threads: int, num_predict: int) -> tuple[int, float]:
    from minutes.providers.ollama import OllamaProvider

    os.environ["OLLAMA_NUM_THREAD"] = str(threads)
    os.environ["OLLAMA_NUM_PREDICT"] = str(num_predict)
    p = OllamaProvider(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
                       model=model)
    started = time.monotonic()
    text = p.generate(PROMPT)
    return len(text), time.monotonic() - started


def main(argv: list[str] | None = None) -> int:
    from minutes.config import load_dotenv

    load_dotenv()
    ap = argparse.ArgumentParser(prog="bench_llm", description="로컬 LLM tok/s 측정")
    ap.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"),
                    help="쉼표로 여러 개 (예: qwen2.5:3b,qwen2.5:7b)")
    ap.add_argument("--threads", default="0", help="쉼표로 여러 개 (0=Ollama 기본)")
    ap.add_argument("--num-predict", type=int, default=256, help="생성 토큰 수(측정용)")
    args = ap.parse_args(argv)

    print(f"host={os.environ.get('OLLAMA_HOST', 'http://localhost:11434')}"
          f"  입력={len(PROMPT):,}자  생성상한={args.num_predict}토큰\n")
    print(f"{'모델':<16} {'스레드':>6} {'글자':>7} {'초':>7} {'평가'}")
    print("─" * 62)

    for model in [m.strip() for m in args.model.split(",") if m.strip()]:
        for t in [int(x) for x in args.threads.split(",")]:
            try:
                chars, sec = bench(model, t, args.num_predict)
            except Exception as e:  # noqa: BLE001  한 조합이 실패해도 나머지는 본다
                print(f"{model:<16} {t or '자동':>6} {'—':>7} {'—':>7} 실패: {e}")
                continue
            # 콘솔에 이미 tok/s 가 찍히므로 여기서는 판정만 덧붙인다.
            rate = chars / max(sec, 0.001)
            verdict = ("느림 — 전원 모드·여유 RAM 확인" if rate < 8
                       else "보통" if rate < 20 else "양호")
            print(f"{model:<16} {t or '자동':>6} {chars:>7,} {sec:>7.1f} {verdict}")

    print("\n느리면(≈2 tok/s) 이 순서로 확인하세요:")
    print("  1) 전원 모드: 설정 → 시스템 → 전원 → '최고의 성능'  (절전이면 클럭이 반토막)")
    print("  2) 여유 RAM: 작업 관리자 → 성능 → 메모리. 80% 넘으면 `wsl --shutdown`")
    print("  3) 스레드: 위 표에서 가장 빠른 값을 .env 의 OLLAMA_NUM_THREAD 에 넣기")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
