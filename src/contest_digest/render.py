"""render 단계: 다이제스트 Issue 마크다운."""

from __future__ import annotations

from datetime import date, timedelta

from .models import Contest, OtherDate

SOURCE_NAMES = {"wevity": "위비티", "linkareer": "링커리어"}


def _esc(text: str | None) -> str:
    if not text:
        return "-"
    return " ".join(text.split()).replace("|", "\\|")


def _dday(end: str | None, today: date) -> str:
    if not end:
        return "마감일 미확인"
    d = (date.fromisoformat(end) - today).days
    label = "D-day" if d == 0 else f"D-{d}"
    return f"{end} ({label})"


def _period(d: OtherDate) -> str:
    if d.date and d.end_date and d.end_date != d.date:
        return f"{d.date} ~ {d.end_date}"
    return d.date or d.end_date or d.note or "?"


def _block(c: Contest, today: date) -> str:
    lines = [f"### [{_esc(c.title)}]({c.source_url})"]
    meta = [f"**마감** {_dday(c.apply_end, today)}", f"**주최** {_esc(c.host)}"]
    if c.category:
        meta.append(f"**분야** {_esc(c.category)}")
    lines.append(" · ".join(meta))
    if c.topic:
        lines.append(f"> {_esc(c.topic)}")
    rows = [
        ("접수", f"{c.apply_start or '?'} ~ {c.apply_end or '?'}" if (c.apply_start or c.apply_end) else None),
        ("상금", "; ".join(filter(None, [c.prize_total, ", ".join(c.prize_details) or None])) or None),
        ("참가 자격", c.eligibility),
        ("팀 구성", c.team_size),
        ("제출물", c.submission),
        ("기타 일정", ", ".join(f"{d.label} {_period(d)}" for d in c.other_dates) or None),
    ]
    for name, value in rows:
        if value:
            lines.append(f"- {name}: {_esc(value)}")
    links = [f"[원문]({c.source_url})"] + [f"[포스터{i + 1}]({u})" for i, u in enumerate(c.poster_urls)]
    lines.append(f"- 링크: {' · '.join(links)} ({SOURCE_NAMES.get(c.key.split(':')[0], '')})")
    if c.needs_review:
        lines.append(f"- ⚠️ 확인 필요: {_esc('; '.join(c.review_reasons))}")
    return "\n".join(lines)


def week_of_month(d: date) -> tuple[int, int]:
    """(월, 주차). 월~일 한 주를 그 주 목요일이 속한 달의 주로 본다 (ISO 8601과 같은 기준).

    예: 2026-11-30(월)이 속한 주의 목요일은 12-03이므로 (12, 1).
    """
    thursday = d + timedelta(days=3 - d.weekday())
    return thursday.month, (thursday.day - 1) // 7 + 1


def title(contests: list[Contest], today: date) -> str:
    month, week = week_of_month(today)
    return f"주간 공모전 - {month}월 {week}째주 IT·AI 공모전"


def render(contests: list[Contest], today: date, urgent_days: int = 7) -> str:
    def end(c: Contest) -> date:
        return date.fromisoformat(c.apply_end) if c.apply_end else date.max

    ordered = sorted(contests, key=lambda c: (end(c), c.key))
    urgent = [c for c in ordered if (end(c) - today).days <= urgent_days and end(c) != date.max]
    rest = [c for c in ordered if c not in urgent]

    out = [
        f"이번 주 새로 수집된 IT·데이터·AI 공모전 **{len(contests)}건**입니다.",
        "",
        "> 아래 정보는 원문과 포스터를 AI로 요약한 것이라 틀릴 수 있습니다. 지원 전에 꼭 원문을 확인하세요.",
        "",
    ]
    if urgent:
        out += [f"## ⏰ 마감 임박 ({urgent_days}일 이내)", ""]
        out += [_block(c, today) + "\n" for c in urgent]
    if rest:
        out += ["## 📋 신규 공모전 (마감순)", ""]
        out += [_block(c, today) + "\n" for c in rest]
    out += [
        "---",
        "<sub>출처: 위비티, 링커리어. 원문 본문과 포스터는 재게시하지 않고 링크만 겁니다.</sub>",
    ]
    return "\n".join(out)
