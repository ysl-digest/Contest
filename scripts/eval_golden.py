"""정답 JSON과 VLM 추출 결과를 필드별로 비교한다. 실제 네트워크·API를 쓰므로 CI에서는 돌리지 않는다.

사용: OPENROUTER_API_KEY=... python scripts/eval_golden.py [tests/golden]
정답 파일 형식: {"source": "wevity", "id": "111768", "url": "...", "title": "...", "expected": {필드: 값}}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from contest_digest.config import Settings, today_kst
from contest_digest.extract import Extractor
from contest_digest.http import HttpClient
from contest_digest.models import Listing
from contest_digest.sources import SOURCES

FIELDS = ["host", "apply_start", "apply_end", "prize_total", "team_size", "category"]


def norm(v):
    return " ".join(str(v).split()).lower() if v is not None else None


def main(golden_dir: str = "tests/golden") -> int:
    settings = Settings()
    http = HttpClient(settings.user_agent, delay=settings.request_delay)
    extractor = Extractor(settings, http)
    today = today_kst().date()
    hit = total = 0
    for path in sorted(Path(golden_dir).glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        listing = Listing(case["source"], case["id"], case.get("title", ""), case["url"])
        detail = SOURCES[case["source"]](http).fetch(listing)
        got = extractor.extract(detail, today).model_dump()
        for field in FIELDS:
            if field not in case["expected"]:
                continue
            ok = norm(got.get(field)) == norm(case["expected"][field])
            hit += ok
            total += 1
            if not ok:
                print(f"✗ {path.name} {field}: 기대 {case['expected'][field]!r} / 결과 {got.get(field)!r}")
    print(f"정확도 {hit}/{total} ({hit / total:.0%})" if total else "정답 파일 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
