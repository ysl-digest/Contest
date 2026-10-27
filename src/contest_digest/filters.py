"""dedupe 단계(마감·기처리 제외)와 키워드 기반 IT 판정(classify 대체 규칙)."""

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


_BRACKETS = re.compile(r"[\[\(【<（][^\]\)】>）]*[\]\)】>）]")
_NON_WORD = re.compile(r"[^0-9a-z가-힣]")


def title_key(title: str) -> str:
    """소스 간 같은 공모전을 찾기 위한 정규화 제목. 괄호 안 부연과 기호·공백을 뺀다."""
    return _NON_WORD.sub("", _BRACKETS.sub("", title.lower()))


def select_new(listings: list[Listing], seen: set[str], today: date,
               seen_titles: set[str] = frozenset()) -> list[Listing]:
    """미처리·접수 중인 건을 마감순으로. 제목이 같은 건(다른 소스 포함)은 하나만 남긴다."""
    out: dict[str, Listing] = {}
    titles = set(seen_titles)
    for it in sorted(listings, key=lambda x: x.key):
        tkey = title_key(it.title)
        if it.key in seen or it.key in out or (tkey and tkey in titles):
            continue
        if is_open(it, today):
            out[it.key] = it
            titles.add(tkey)
    return sorted(out.values(), key=lambda x: (x.apply_end or date.max, x.key))
