"""dedupe 단계: 분야 필터, 마감 필터, 이미 처리한 건 제외."""

from __future__ import annotations

import re
from datetime import date

from .config import IT_KEYWORDS, IT_ONLY_CATEGORIES
from .models import Listing

_ASCII = re.compile(r"[a-z]+")


def _keyword_pattern(words: list[str]) -> re.Pattern:
    parts = []
    for w in words:
        if _ASCII.fullmatch(w):
            parts.append(rf"(?<![a-z]){re.escape(w)}(?![a-z])")
        else:
            parts.append(re.escape(w))
    return re.compile("|".join(parts), re.I)


_IT_PATTERN = _keyword_pattern(IT_KEYWORDS)


def is_it_related(listing: Listing) -> bool:
    if _IT_PATTERN.search(listing.title):
        return True
    cats = set(listing.categories)
    # "기타"만 있는 건 근거가 부족하므로 제외
    return bool(cats) and cats <= IT_ONLY_CATEGORIES and cats != {"기타"}


def is_open(listing: Listing, today: date) -> bool:
    """마감일을 모르면 일단 통과시키고, 상세 단계에서 다시 확인한다."""
    return listing.apply_end is None or listing.apply_end >= today


def select_new(listings: list[Listing], seen: set[str], today: date) -> list[Listing]:
    out: dict[str, Listing] = {}
    for it in listings:
        if it.key in seen or it.key in out:
            continue
        if is_open(it, today) and is_it_related(it):
            out[it.key] = it
    return sorted(out.values(), key=lambda x: (x.apply_end or date.max, x.key))
