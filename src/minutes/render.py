"""회의록(Minutes) → Markdown 렌더링."""

from __future__ import annotations

from .schema import Minutes


def render_markdown(m: Minutes) -> str:
    L: list[str] = []
    L.append(f"# {m.meeting_title or '회의록'}")
    L.append("")
    if m.date:
        L.append(f"- **일시**: {m.date}")
    if m.attendees:
        L.append(f"- **참석자**: {', '.join(m.attendees)}")
    L.append("")

    if m.agenda:
        L.append("## 안건")
        L.extend(f"{i}. {a}" for i, a in enumerate(m.agenda, 1))
        L.append("")

    if m.discussion:
        L.append("## 논의 내용")
        for d in m.discussion:
            L.append(f"### {d.topic}")
            L.append(d.summary)
            L.append("")

    L.append("## 결정 사항")
    if m.decisions:
        for d in m.decisions:
            line = f"- {d.content}"
            if d.rationale:
                line += f" _(근거: {d.rationale})_"
            L.append(line)
    else:
        L.append("- (명시적 결정 없음)")
    L.append("")

    L.append("## 액션 아이템")
    if m.action_items:
        L.append("| 할 일 | 담당자 | 기한 | 상태 |")
        L.append("|---|---|---|---|")
        for a in m.action_items:
            L.append(
                f"| {a.task} | {a.owner or '-'} | {a.due_date or '-'} | {a.status or '-'} |"
            )
    else:
        L.append("- (지정된 액션 아이템 없음)")
    L.append("")

    if m.open_issues:
        L.append("## 미결 사항")
        L.extend(f"- {x}" for x in m.open_issues)
        L.append("")

    if m.risks:
        L.append("## 리스크")
        L.extend(f"- {x}" for x in m.risks)
        L.append("")

    return "\n".join(L).rstrip() + "\n"
