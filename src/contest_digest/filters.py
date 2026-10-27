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


def title_keys(title: str) -> set[str]:
    """소스 간 같은 공모전을 찾기 위한 정규화 제목들.

    소스마다 부제를 괄호·따옴표 등 다르게 표기하므로 ① 괄호 안 부연을 뺀 것 ② 기호만 뺀 것
    두 가지를 만들고, 하나라도 겹치면 같은 공모전으로 본다.
    """
    t = title.lower()
    return {k for k in (_NON_WORD.sub("", _BRACKETS.sub("", t)), _NON_WORD.sub("", t)) if k}


def select_new(listings: list[Listing], seen: set[str], today: date,
               seen_titles: set[str] = frozenset()) -> list[Listing]:
    """미처리·접수 중인 건을 마감순으로. 제목이 같은 건(다른 소스 포함)은 하나만 남긴다."""
    out: dict[str, Listing] = {}
    titles = set(seen_titles)
    for it in sorted(listings, key=lambda x: x.key):
        tkeys = title_keys(it.title)
        if it.key in seen or it.key in out or tkeys & titles:
            continue
        if is_open(it, today):
            out[it.key] = it
            titles |= tkeys
    return sorted(out.values(), key=lambda x: (x.apply_end or date.max, x.key))
