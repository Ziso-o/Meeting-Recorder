"""회의록 문체 — 개조식(명사형 종결 · 마침표 없음) 보정.

어체 자체는 프롬프트가 만든다(`prompts/03_integrate_minutes.md`). 다만 로컬
소형 LLM은 지시를 흘리기 쉬워서, **마침표만은 코드에서 결정적으로 제거**한다.
서술형→명사형 변환은 형태소 분석이 필요해 코드로 하지 않는다 — 그건 프롬프트의 몫.

`MINUTES_STRIP_PERIODS=0` 이면 이 보정을 끈다(프롬프트를 서술체로 바꿔 쓸 때).
"""

from __future__ import annotations

import os
import re

# 숫자 뒤(`1.5억`)·버전(`v3.1`)·날짜를 건드리지 않도록, 마침표 **앞**이
# 한글/영문/닫는 괄호인 경우로 한정한다.
_LEAD = r"(?<=[가-힣A-Za-z\)\]」』”])"
#: 문장 **사이**의 마침표 → 줄바꿈. 개조식은 항목마다 줄을 나눈다
#: (그냥 지우면 "…내려짐 실증 구역은…" 처럼 두 문장이 붙어버린다).
_BETWEEN = re.compile(_LEAD + r"\.[ \t]+")
#: 줄 **끝**의 마침표 → 제거
_TAIL = re.compile(_LEAD + r"\.[ \t]*$", re.MULTILINE)


def strip_enabled() -> bool:
    return os.environ.get("MINUTES_STRIP_PERIODS", "1").lower() not in ("0", "false", "off", "no")


def strip_sentence_periods(text: str) -> str:
    """개조식 문장 끝의 마침표를 없앤다.

    문장이 여러 개면 줄을 나눈다. 소수점·버전·날짜의 점은 그대로 둔다.
    """
    if not text or not strip_enabled():
        return text
    return _TAIL.sub("", _BETWEEN.sub("\n", text))
