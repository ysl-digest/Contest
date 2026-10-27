"""처리한 공모전 ID를 저장소 내 JSON으로 관리한다."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


class State:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.items: dict[str, dict] = data.get("items", {})
        self.last_run: str | None = data.get("last_run")

    @classmethod
    def load(cls, path: Path) -> "State":
        if not path.exists():
            return cls()
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def seen(self) -> set[str]:
        return set(self.items)

    def seen_titles(self) -> set[str]:
        from .filters import title_keys

        return {k for v in self.items.values() if v.get("title") for k in title_keys(v["title"])}

    def mark(self, key: str, today: date, apply_end: date | None, issue_number: int | None,
             title: str | None = None, is_it: bool | None = None) -> None:
        self.items[key] = {
            "title": title,
            "first_seen": today.isoformat(),
            "apply_end": apply_end.isoformat() if apply_end else None,
            "it": is_it,
            "issue": issue_number,
        }

    def prune(self, today: date, retention_days: int) -> None:
        """마감 후 retention_days가 지난 항목을 지운다. 마감일을 모르면 first_seen 기준."""
        cutoff = today - timedelta(days=retention_days)
        keep = {}
        for key, v in self.items.items():
            ref = v.get("apply_end") or v.get("first_seen")
            if ref and date.fromisoformat(ref) < cutoff:
                continue
            keep[key] = v
        self.items = keep

    def save(self, path: Path, today: date) -> None:
        # 신규 0건이어도 last_run이 바뀌어 커밋이 생긴다 (scheduled workflow 비활성화 방지)
        self.last_run = today.isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"last_run": self.last_run, "items": dict(sorted(self.items.items()))}
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
