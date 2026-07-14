"""glossary.yaml 로딩 및 프롬프트 주입용 문자열 생성."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_glossary(path: str | Path = "glossary.yaml") -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    import yaml  # 지연 임포트

    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data or {}


def glossary_to_prompt(glossary: dict[str, Any]) -> str:
    """glossary dict를 LLM 프롬프트에 넣기 좋은 사람이 읽는 텍스트로 변환한다."""
    lines: list[str] = []

    def _add(header: str, items: list[Any] | None) -> None:
        if not items:
            return
        lines.append(f"[{header}]")
        for it in items:
            if isinstance(it, dict):
                term = it.get("term", "")
                aliases = it.get("aliases", [])
                if aliases:
                    lines.append(f"- {term} (오인식 예: {', '.join(aliases)})")
                else:
                    lines.append(f"- {term}")
            else:
                lines.append(f"- {it}")

    _add("사업명", glossary.get("projects"))
    _add("기관명", glossary.get("organizations"))
    _add("기술 약어", glossary.get("acronyms"))
    _add("인명/직책", glossary.get("people"))

    return "\n".join(lines) if lines else "(등록된 용어 없음)"
