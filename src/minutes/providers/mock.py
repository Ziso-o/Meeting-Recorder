"""MockProvider — 테스트/오프라인용. 네트워크 없이 결정적 응답을 만든다.

프롬프트에 박힌 스테이지 마커(`<!-- stage: xxx -->`)를 읽어 단계별로 응답을 라우팅한다.
- term_correction : 입력 세그먼트 텍스트를 그대로 반환(JSON 배열)
- chunk_summary   : 청크 텍스트에서 뽑은 간단한 요약 문자열
- integrate       : 스키마를 만족하는 유효 JSON 회의록

`fail_integrate_once=True`이면 통합 단계에서 첫 호출에 깨진 JSON을 반환해
체인의 '검증 실패 시 1회 재시도' 로직을 검증할 수 있다.
"""

from __future__ import annotations

import json
import re


class MockProvider:
    name = "mock"

    def __init__(self, fail_integrate_once: bool = False) -> None:
        self.fail_integrate_once = fail_integrate_once
        self._integrate_calls = 0
        self.calls: list[str] = []  # 스테이지 호출 기록(테스트 관찰용)

    @staticmethod
    def _stage(prompt: str) -> str:
        m = re.search(r"<!--\s*stage:\s*(\w+)\s*-->", prompt)
        return m.group(1) if m else "unknown"

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int | None = None
    ) -> str:
        stage = self._stage(prompt)
        self.calls.append(stage)

        if stage == "term_correction":
            # 입력 세그먼트 텍스트를 그대로 교정 없이 반환 (JSON 배열).
            texts = re.findall(r'"text"\s*:\s*"([^"]*)"', prompt)
            return json.dumps(texts, ensure_ascii=False)

        if stage == "chunk_summary":
            first_line = next(
                (ln for ln in prompt.splitlines() if ln.strip().startswith("[")),
                "논의 내용",
            )
            return f"[요약] {first_line.strip()[:60]}"

        if stage == "integrate":
            self._integrate_calls += 1
            if self.fail_integrate_once and self._integrate_calls == 1:
                return "여기 회의록입니다: { 깨진 JSON "  # 파싱 실패 유도
            return json.dumps(
                {
                    "meeting_title": "테스트 회의",
                    "date": "2026-07-14",
                    "attendees": ["홍길동", "김철수"],
                    "agenda": ["안건 A", "안건 B"],
                    "discussion": [{"topic": "주제1", "summary": "요약1"}],
                    "decisions": [{"content": "결정1", "rationale": "근거1"}],
                    "action_items": [
                        {
                            "task": "작업1",
                            "owner": "홍길동",
                            "due_date": "2026-07-21",
                            "status": "open",
                        }
                    ],
                    "open_issues": ["미결1"],
                    "risks": ["리스크1"],
                },
                ensure_ascii=False,
            )

        return ""
