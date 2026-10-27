"""링커리어(linkareer.com) 어댑터. 페이지에 내장된 __NEXT_DATA__(Apollo 캐시)를 읽는다."""

from __future__ import annotations

import json
import re
from datetime import date, datetime

from ..config import KST
from ..models import Detail, Listing
from .base import Source, html_to_text

BASE = "https://linkareer.com"
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def list_url(page: int) -> str:
    """전체 분야 목록. IT 여부는 classify 단계에서 판단한다."""
    return f"{BASE}/list/contest?page={page}"


def apollo_state(html: str) -> dict:
    m = NEXT_DATA.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ 없음 (페이지 구조 변경 가능성)")
    data = json.loads(m.group(1))
    state = data.get("props", {}).get("pageProps", {}).get("__APOLLO_STATE__")
    if not isinstance(state, dict):
        raise ValueError("__APOLLO_STATE__ 없음 (페이지 구조 변경 가능성)")
    return state


def ms_to_date(ms: int | None) -> date | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, KST).date()


def _deref(state: dict, ref) -> dict:
    if isinstance(ref, dict) and "__ref" in ref:
        return state.get(ref["__ref"], {})
    return ref or {}


def parse_list(html: str) -> list[Listing]:
    state = apollo_state(html)
    items = []
    for key, act in state.items():
        if not key.startswith("Activity:") or act.get("activityTypeID") != 3:
            continue
        cats = [_deref(state, c).get("name", "") for c in act.get("categories") or []]
        items.append(
            Listing(
                source="linkareer",
                id=str(act["id"]),
                title=act.get("title", "").strip(),
                url=f"{BASE}/activity/{act['id']}",
                host=act.get("organizationName"),
                apply_end=ms_to_date(act.get("recruitCloseAt")),
                categories=[c for c in cats if c],
            )
        )
    return items


def parse_detail(html: str, listing: Listing) -> Detail:
    state = apollo_state(html)
    act = state.get(f"Activity:{listing.id}")
    if not act:
        raise ValueError(f"Activity:{listing.id} 없음")
    body = _deref(state, act.get("detailText")).get("text", "")
    cats = [_deref(state, c).get("name") for c in act.get("categories") or []]
    targets = [_deref(state, t).get("name") for t in act.get("targets") or []]
    benefits = [_deref(state, b).get("name") for b in act.get("benefits") or []]
    reward = act.get("tenThousandUnitOfReward")
    meta = [
        f"제목: {act.get('title')}",
        f"주최: {act.get('organizationName')} ({act.get('organizationType') or '-'})",
        f"분야: {', '.join(filter(None, cats))}",
        f"대상: {', '.join(filter(None, targets))}",
        f"접수: {ms_to_date(act.get('recruitStartAt'))} ~ {ms_to_date(act.get('recruitCloseAt'))}",
        f"시상 규모: {reward}만원" if reward else "시상 규모: -",
        f"혜택: {', '.join(filter(None, benefits))}",
    ]
    if act.get("homepageURL"):
        meta.append(f"홈페이지: {act['homepageURL']}")
    posters = []
    thumb = _deref(state, act.get("thumbnailImage")).get("url")
    if thumb:
        posters.append(thumb)
    for f in act.get("files") or []:
        fd = _deref(state, f)
        url = fd.get("url")
        if url and url not in posters and str(fd.get("filename", "")).lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            posters.append(url)
    text = "[요약 정보]\n" + "\n".join(meta) + "\n\n[상세 내용]\n" + html_to_text(body)
    return Detail(listing=listing, text=text, poster_urls=posters,
                  apply_start=ms_to_date(act.get("recruitStartAt")),
                  apply_end=ms_to_date(act.get("recruitCloseAt")), referer=listing.url)


class LinkareerSource(Source):
    name = "linkareer"

    def collect(self) -> list[Listing]:
        seen: dict[str, Listing] = {}
        for page in range(1, self.max_pages + 1):
            items = parse_list(self.client.get_text(list_url(page)))
            if not items or all(it.id in seen for it in items):
                break
            for it in items:
                seen.setdefault(it.id, it)
        return list(seen.values())

    def fetch(self, listing: Listing) -> Detail:
        return parse_detail(self.client.get_text(listing.url), listing)
