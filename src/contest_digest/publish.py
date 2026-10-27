"""publish 단계: 발행 저장소에 GitHub Issue 생성. 상태 파일 커밋은 코드 저장소 워크플로의 git 단계가 맡는다."""

from __future__ import annotations

import requests

API = "https://api.github.com"


def create_issue(token: str, repo: str, title: str, body: str, labels: list[str]) -> int:
    if not token:
        raise RuntimeError("ISSUE_TOKEN이 없습니다 (발행 저장소의 Issues 쓰기 권한이 있는 토큰 필요)")
    resp = requests.post(
        f"{API}/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"title": title, "body": body, "labels": labels},
        timeout=30,
    )
    resp.raise_for_status()
    return int(resp.json()["number"])
