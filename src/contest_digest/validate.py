"""validate 단계: VLM 출력 검증과 수집 메타데이터와의 대조."""

from __future__ import annotations

from datetime import date, timedelta

from .models import Contest, Detail, Extraction


class ValidationError(Exception):
    pass


def _parse_date(value: str | None, field: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} 형식 오류: {value!r}") from exc


def check(ext: Extraction, today: date) -> None:
    """형식/범위 위반이면 ValidationError. 재시도 대상."""
    if not ext.title.strip():
        raise ValidationError("title 비어 있음")
    lo, hi = today - timedelta(days=366), today + timedelta(days=730)
    start = _parse_date(ext.apply_start, "apply_start")
    end = _parse_date(ext.apply_end, "apply_end")
    for name, d in (("apply_start", start), ("apply_end", end)):
        if d and not lo <= d <= hi:
            raise ValidationError(f"{name} 범위 밖: {d}")
    if start and end and end < start:
        raise ValidationError(f"apply_end({end}) < apply_start({start})")
    for od in ext.other_dates:
        _parse_date(od.date, f"other_dates[{od.label}]")


def finalize(ext: Extraction | None, detail: Detail, reasons: list[str]) -> Contest:
    """수집 데이터로 URL·마감일을 보정하고 needs_review를 결정한다."""
    listing = detail.listing
    reasons = list(reasons)
    if ext is None:
        ext = Extraction(title=listing.title, host=listing.host)
    data = ext.model_dump()
    meta_end = detail.apply_end or listing.apply_end
    if meta_end:
        if ext.apply_end and ext.apply_end != meta_end.isoformat():
            reasons.append(f"마감일 불일치: 원문 메타 {meta_end} / 추출 {ext.apply_end} (메타 우선)")
        data["apply_end"] = meta_end.isoformat()
    elif not ext.apply_end:
        reasons.append("마감일 확인 불가")
    if detail.apply_start and not data.get("apply_start"):
        data["apply_start"] = detail.apply_start.isoformat()
    data["host"] = data.get("host") or listing.host
    return Contest(
        **data,
        key=listing.key,
        source_url=listing.url,
        poster_urls=detail.poster_urls,
        needs_review=bool(reasons),
        review_reasons=reasons,
    )
