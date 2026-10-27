"""collect → dedupe → classify → fetch → extract/validate → render 오케스트레이션."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from .classify import Classifier, Verdict, classify_by_keyword
from .config import Settings
from .extract import Extractor, metadata_only
from .filters import select_new
from .http import HttpClient
from .models import Contest, Listing
from .render import render, title
from .sources import SOURCES
from .state import State

log = logging.getLogger(__name__)


@dataclass
class Mark:
    """상태 파일에 기록할 항목. 발송한 건은 Issue 번호가 나중에 채워진다."""

    listing: Listing
    is_it: bool
    apply_end: date | None = None


@dataclass
class RunResult:
    contests: list[Contest] = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)
    verdicts: dict[str, Verdict] = field(default_factory=dict)
    titles: dict[str, str] = field(default_factory=dict)
    collected: int = 0
    failures: dict[str, str] = field(default_factory=dict)
    deferred: int = 0
    title: str = ""
    body: str = ""

    @property
    def non_it(self) -> int:
        return sum(1 for m in self.marks if not m.is_it)


def collect(http: HttpClient, settings: Settings, names: list[str]) -> tuple[list[Listing], dict[str, str]]:
    listings, failures = [], {}
    for name in names:
        try:
            got = SOURCES[name](http, settings.max_pages).collect()
            log.info("%s: %d건 수집", name, len(got))
            listings += got
        except Exception as exc:  # noqa: BLE001 - 소스 하나가 실패해도 계속
            log.exception("%s 수집 실패", name)
            failures[name] = f"{type(exc).__name__}: {exc}"
    return listings, failures


def run(settings: Settings, http: HttpClient, state: State, today: date, names: list[str],
        use_llm: bool = True, extractor: Extractor | None = None,
        classifier: Classifier | None = None) -> RunResult:
    result = RunResult()
    listings, result.failures = collect(http, settings, names)
    result.collected = len(listings)
    new = select_new(listings, state.seen(), today, state.seen_titles())

    # classify: 전체 신규 건을 IT/비IT로 나눈다. 비IT는 상태에만 기록하고 발송하지 않는다.
    if use_llm and classifier is None:
        classifier = Classifier(settings)
    result.verdicts = classifier.classify(new) if classifier else classify_by_keyword(new)
    result.titles = {it.key: it.title for it in new}
    it_items = []
    for listing in new:
        if result.verdicts[listing.key].is_it:
            it_items.append(listing)
        else:
            result.marks.append(Mark(listing, False, listing.apply_end))
    result.deferred = max(0, len(it_items) - settings.max_items)
    it_items = it_items[: settings.max_items]
    log.info("신규 %d건 중 IT %d건 처리 (비IT %d건, 이월 %d건)",
             len(new), len(it_items), result.non_it, result.deferred)

    if use_llm and extractor is None:
        extractor = Extractor(settings, http)
    sources = {name: SOURCES[name](http, settings.max_pages) for name in names}
    for listing in it_items:
        try:
            detail = sources[listing.source].fetch(listing)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s 상세 수집 실패: %s", listing.key, exc)
            continue  # 상태에 기록하지 않아 다음 실행에서 다시 시도
        end = detail.apply_end or listing.apply_end
        if end and end < today:
            result.marks.append(Mark(listing, True, end))
            continue
        contest = extractor.extract(detail, today) if extractor else metadata_only(detail)
        if contest.category == "비IT":  # 상세를 보고 나서야 비IT로 드러난 경우
            result.marks.append(Mark(listing, False, end))
            continue
        result.contests.append(contest)
        result.marks.append(Mark(listing, True, end))

    result.title = title(result.contests, today)
    result.body = render(result.contests, today, result.failures, settings.urgent_days, result.deferred)
    return result


def save_marks(state: State, result: RunResult, today: date, issue: int | None) -> None:
    sent = {c.key for c in result.contests}
    for m in result.marks:
        state.mark(m.listing.key, today, m.apply_end, issue if m.listing.key in sent else None,
                   title=m.listing.title, is_it=m.is_it)
