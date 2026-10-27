"""--offline 실행용: 네트워크 대신 tests/fixtures의 HTML을 돌려주는 HTTP 클라이언트."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .config import KST, ROOT, today_kst

FIXTURES = ROOT / "tests" / "fixtures"
EMPTY_LINKAREER = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"__APOLLO_STATE__":{}}}}</script>'


_TOKEN = re.compile(r"\{\{(DATE|MS)([+-]\d+)\}\}")


def render_fixture(text: str, today: date) -> str:
    """fixture 안의 {{DATE+N}}, {{MS+N}}을 today 기준 날짜로 바꾼다 (fixture가 낡지 않도록)."""

    def sub(m: re.Match) -> str:
        d = today + timedelta(days=int(m.group(2)))
        if m.group(1) == "DATE":
            return d.isoformat()
        end_of_day = datetime.combine(d, time(23, 59, 59), KST)
        return str(int(end_of_day.timestamp() * 1000))

    return _TOKEN.sub(sub, text)


class FixtureResponse:
    def __init__(self, text: str = "", content: bytes = b""):
        self.text = text
        self.content = content or text.encode()


class FixtureHttp:
    def __init__(self, root: Path = FIXTURES, today: date | None = None):
        self.root = root
        self.today = today or today_kst().date()

    def _path(self, url: str) -> Path | None:
        if "wevity.com" in url:
            if "gbn=view" in url:
                return self.root / "wevity_detail.html"
            return self.root / "wevity_list.html" if re.search(r"gp=1\b", url) and "cidx=20" in url else None
        if "linkareer.com/list" in url:
            return self.root / "linkareer_list.html" if "page=1" in url and "filterBy" in url else None
        m = re.search(r"linkareer\.com/activity/(\d+)", url)
        if m:
            return self.root / f"linkareer_detail_{m.group(1)}.html"
        return None

    def get_text(self, url: str) -> str:
        path = self._path(url)
        if path is None:  # 다음 페이지 없음
            return EMPTY_LINKAREER if "linkareer" in url else "<html></html>"
        return render_fixture(path.read_text(encoding="utf-8"), self.today)

    def get(self, url: str, referer: str | None = None) -> FixtureResponse:
        if url.endswith((".jpg", ".png")) or "attachments" in url:
            return FixtureResponse(content=(self.root / "poster.png").read_bytes())
        return FixtureResponse(self.get_text(url))
