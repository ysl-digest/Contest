"""render 단계: 다이제스트 Issue 마크다운."""

from __future__ import annotations

from datetime import date

from .models import Contest

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
        ("기타 일정", ", ".join(f"{d.label} {d.date or d.note or '?'}" for d in c.other_dates) or None),
    ]
    for name, value in rows:
        if value:
            lines.append(f"- {name}: {_esc(value)}")
    links = [f"[원문]({c.source_url})"] + [f"[포스터{i + 1}]({u})" for i, u in enumerate(c.poster_urls)]
    lines.append(f"- 링크: {' · '.join(links)} ({SOURCE_NAMES.get(c.key.split(':')[0], '')})")
    if c.needs_review:
        lines.append(f"- ⚠️ 확인 필요: {_esc('; '.join(c.review_reasons))}")
    return "\n".join(lines)


def title(contests: list[Contest], today: date) -> str:
    return f"[공모전 주간] {today.isoformat()} ({len(contests)}건)"


def render(contests: list[Contest], today: date, failures: dict[str, str], urgent_days: int = 7,
           deferred: int = 0) -> str:
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
    notes = []
    if deferred:
        notes.append(f"- 처리 상한을 넘은 {deferred}건은 다음 주에 발송합니다.")
    for src, err in failures.items():
        notes.append(f"- {SOURCE_NAMES.get(src, src)} 수집 실패: {_esc(err)[:200]}")
    if notes:
        out += ["## 운영 메모", ""] + notes + [""]
    out += [
        "---",
        "구독: 저장소 **Watch → Custom → Issues** · 구독 취소: **Unwatch**",
        "",
        "<sub>출처: 위비티, 링커리어. 원문 본문과 포스터는 재게시하지 않고 링크만 겁니다.</sub>",
    ]
    return "\n".join(out)
