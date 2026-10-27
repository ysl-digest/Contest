"""호스트별 지연과 재시도를 적용한 HTTP 클라이언트."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)


class HttpClient:
    def __init__(self, user_agent: str, delay: float = 2.0, timeout: float = 20.0, retries: int = 2):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self._last: dict[str, float] = {}

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        elapsed = time.monotonic() - self._last.get(host, 0.0)
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last[host] = time.monotonic()

    def get(self, url: str, referer: str | None = None) -> requests.Response:
        headers = {"Referer": referer} if referer else {}
        for attempt in range(self.retries + 1):
            self._wait(url)
            try:
                resp = self.session.get(url, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                if attempt == self.retries:
                    raise
                log.warning("GET %s 실패 (%s), 재시도 %d", url, exc, attempt + 1)
                time.sleep(2 ** attempt)
        raise AssertionError("unreachable")

    def get_text(self, url: str) -> str:
        resp = self.get(url)
        resp.encoding = resp.encoding if resp.encoding and resp.encoding.lower() != "iso-8859-1" else "utf-8"
        return resp.text
