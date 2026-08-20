"""OllamaProvider — 로컬 LLM (민감/B2G 회의, profile=secure).

네트워크가 로컬 Ollama 서버(기본 http://localhost:11434)로만 나간다.
httpx는 지연 임포트하여 테스트(mock 사용)에서는 불필요하게 요구하지 않는다.
"""

from __future__ import annotations

import json
import os
import time


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen2.5:14b",
        timeout: float | None = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        # CPU 로컬 LLM은 느리다 — 기본을 넉넉히 두고 환경변수로 조정 가능하게.
        self.timeout = timeout if timeout is not None else float(
            os.environ.get("OLLAMA_TIMEOUT", "1800")
        )
        self.max_ctx = int(os.environ.get("OLLAMA_MAX_CTX", "16384"))
        # 출력 상한. 없으면 소형 모델이 반복 생성으로 컨텍스트를 다 채울 때까지 안 멈춘다.
        self.num_predict = int(os.environ.get("OLLAMA_NUM_PREDICT", "2048"))
        # 토큰이 이 시간 동안 안 오면 죽은 것으로 본다(전체 타임아웃과 별개).
        self.stall_timeout = float(os.environ.get("OLLAMA_STALL_TIMEOUT", "180"))
        self.keep_alive = os.environ.get("OLLAMA_KEEP_ALIVE", "10m")
        # 소형 모델은 같은 문구를 반복하기 쉽다 — 기본(1.1)보다 조금 세게.
        self.repeat_penalty = float(os.environ.get("OLLAMA_REPEAT_PENALTY", "1.15"))
        # CPU 스레드. 0이면 Ollama 기본(코어 수 추정)에 맡긴다. P/E 코어가 섞인
        # 노트북 CPU에서는 기본값이 잘못 잡혀 연산이 굶는 경우가 있어 조정 창구를 둔다.
        self.num_thread = int(os.environ.get("OLLAMA_NUM_THREAD", "0"))
        self.output_headroom = self.num_predict

    def context_size(self, prompt: str, output_tokens: int | None = None) -> int:
        """이 프롬프트에 필요한 컨텍스트 크기(토큰).

        **중요**: Ollama 기본 num_ctx(보통 4096)를 넘으면 프롬프트 **앞부분이 조용히
        잘린다** — 회의 앞부분이 통째로 사라진 채 요약이 만들어진다. 속도가 아니라
        정확성 문제라 요청마다 필요한 만큼 명시한다.

        한국어는 대략 1자 ≈ 1토큰(보수적)으로 잡고 출력 여유를 더한다.
        """
        need = int(len(prompt) * 1.1) + (output_tokens or self.output_headroom)
        for size in (4096, 8192, 16384, 32768):
            if need <= size:
                return min(size, self.max_ctx)
        return self.max_ctx

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int | None = None
    ) -> str:
        """생성. **스트리밍**으로 받아 토큰이 끊기는 순간을 바로 잡아낸다.

        통짜 요청(stream=False)이면 모델이 같은 말을 반복하며 폭주해도 타임아웃까지
        아무것도 알 수 없다. 스트리밍이면 토큰 간 간격으로 '죽었는지'를 수 초 안에
        판단할 수 있고, 얼마나 생성했는지도 오류 메시지에 담을 수 있다.
        """
        import httpx  # 지연 임포트

        limit = max_tokens or self.num_predict
        num_ctx = self.context_size(prompt, limit)
        if int(len(prompt) * 1.1) + 512 > num_ctx:
            print(f"  경고: 프롬프트({len(prompt):,}자)가 컨텍스트 한도({num_ctx})를 넘어"
                  " 앞부분이 잘릴 수 있습니다. OLLAMA_MAX_CTX 를 늘리거나"
                  " MINUTES_CHUNK_CHARS 를 줄이세요.")
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": self.keep_alive,   # 청크 사이에 모델을 다시 올리지 않게
            "options": {
                "temperature": 0.2,
                "num_ctx": num_ctx,
                # 출력 상한 — 없으면 소형 모델이 같은 말을 반복하며 컨텍스트를 다 채운다.
                "num_predict": limit,
                "repeat_penalty": self.repeat_penalty,
                **({"num_thread": self.num_thread} if self.num_thread > 0 else {}),
            },
        }
        if system:
            payload["system"] = system

        started = time.monotonic()
        parts: list[str] = []
        tokens = 0
        done_reason = ""
        # read 타임아웃은 **토큰 사이** 간격에 걸린다 — 멈춘 모델을 수 초 안에 잡는다.
        timeout = httpx.Timeout(
            connect=15.0, read=self.stall_timeout, write=60.0, pool=15.0
        )
        try:
            with httpx.stream(
                "POST", f"{self.host}/api/generate", json=payload, timeout=timeout
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    obj = json.loads(line)
                    if obj.get("error"):
                        raise RuntimeError(f"Ollama 오류: {obj['error']}")
                    piece = obj.get("response", "")
                    if piece:
                        parts.append(piece)
                        tokens += 1
                    if obj.get("done"):
                        done_reason = str(obj.get("done_reason") or "")
                        break
                    if time.monotonic() - started > self.timeout:
                        raise TimeoutError(self._slow_message(prompt, started, tokens, limit))
        except httpx.TimeoutException as e:
            raise TimeoutError(self._slow_message(prompt, started, tokens, limit)) from e
        except httpx.HTTPError as e:
            raise RuntimeError(
                f"Ollama 호출 실패 (model={self.model}, host={self.host}): {e}"
            ) from e

        if done_reason == "length":
            # 조용히 잘린 채로 넘어가면 회의록 뒷부분이 사라진다 — 보이게 한다.
            print(f"  경고: 출력이 상한({limit} 토큰)에 걸려 잘렸습니다."
                  " 모델이 요약하지 않고 늘어놓는 중일 수 있습니다"
                  " (프롬프트의 길이 제약을 못 따르는 소형 모델).")
        elapsed = time.monotonic() - started
        print(f"  LLM {self.model}: {tokens:,}토큰 / {elapsed:.0f}초"
              f" ({tokens / max(elapsed, 1):.1f} tok/s)")
        return "".join(parts)

    def _slow_message(self, prompt: str, started: float, tokens: int,
                      limit: int | None = None) -> str:
        """왜 실패했는지 구분해서 알려준다 — 폭주와 무응답은 대처가 다르다."""
        limit = limit or self.num_predict
        elapsed = time.monotonic() - started
        head = (f"Ollama 응답이 {elapsed:.0f}초 안에 끝나지 않았어요"
                f" (model={self.model}, 입력 {len(prompt):,}자, 생성 {tokens:,}토큰).")
        if tokens > limit * 0.8:
            why = ("  · 모델이 같은 말을 반복하며 계속 생성 중일 수 있어요"
                   f" — 출력 상한({limit})을 줄이거나 더 큰 모델을 쓰세요")
        elif tokens == 0:
            why = ("  · 토큰이 하나도 안 나왔어요 — 모델 로딩 중이거나 메모리가 부족합니다."
                   " 작업 관리자에서 여유 RAM을 확인하세요(`wsl --shutdown`으로 확보 가능)")
        else:
            why = f"  · 그냥 느립니다 — 더 작은 모델({self.model} → qwen2.5:3b)을 쓰세요"
        return (f"{head}\n{why}\n"
                f"  · 기다릴 수 있으면 OLLAMA_TIMEOUT을 늘리세요(현재 {self.timeout:.0f}초)")
