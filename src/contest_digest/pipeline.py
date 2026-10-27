"""collect → dedupe → fetch → extract/validate → render → publish 오케스트레이션."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from .config import Settings
from .extract import Extractor, metadata_only
from .http import HttpClient
from .models import Contest, Listing
from .filters import select_new
from .render import render, title
from .sources import SOURCES
from .state import State

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    contests: list[Contest] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # 비IT·마감 등으로 발송하지 않은 키
    failures: dict[str, str] = field(default_factory=dict)
    deferred: int = 0
    title: str = ""
    body: str = ""


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
        use_llm: bool = True, extractor: Extractor | None = None) -> RunResult:
    result = RunResult()
    listings, result.failures = collect(http, settings, names)
    new = select_new(listings, state.seen(), today)
    result.deferred = max(0, len(new) - settings.max_items)
    new = new[: settings.max_items]
    log.info("신규 %d건 처리 (이월 %d건)", len(new), result.deferred)

    if use_llm and extractor is None:
        extractor = Extractor(settings, http)
    sources = {name: SOURCES[name](http, settings.max_pages) for name in names}
    for listing in new:
        try:
            detail = sources[listing.source].fetch(listing)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s 상세 수집 실패: %s", listing.key, exc)
            continue  # 상태에 기록하지 않아 다음 실행에서 다시 시도
        end = detail.apply_end or listing.apply_end
        if end and end < today:
            result.skipped.append(listing.key)
            continue
        contest = extractor.extract(detail, today) if extractor else metadata_only(detail)
        if contest.category == "비IT":
            result.skipped.append(listing.key)
            continue
        result.contests.append(contest)

    result.title = title(result.contests, today)
    result.body = render(result.contests, today, result.failures, settings.urgent_days, result.deferred)
    return result
