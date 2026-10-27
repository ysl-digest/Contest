"""publish 단계: 발행 저장소에 GitHub Issue 생성. 상태 파일 커밋은 코드 저장소 워크플로의 git 단계가 맡는다.

구독자 메일 오염 방지:
- 발행한 Issue는 바로 잠가서(lock) 협업자 외에는 댓글을 달 수 없게 한다 (Issues 쓰기 권한).
- 저장소 상호작용 제한(협업자만)을 매 실행마다 6개월로 갱신한다 (Administration 쓰기 권한).
"""

from __future__ import annotations

import requests

API = "https://api.github.com"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def create_issue(token: str, repo: str, title: str, body: str, labels: list[str]) -> int:
    if not token:
        raise RuntimeError("ISSUE_TOKEN이 없습니다 (발행 저장소의 Issues 쓰기 권한이 있는 토큰 필요)")
    resp = requests.post(
        f"{API}/repos/{repo}/issues",
        headers=_headers(token),
        json={"title": title, "body": body, "labels": labels},
        timeout=30,
    )
    resp.raise_for_status()
    return int(resp.json()["number"])


def lock_issue(token: str, repo: str, number: int) -> None:
    resp = requests.put(f"{API}/repos/{repo}/issues/{number}/lock", headers=_headers(token), timeout=30)
    resp.raise_for_status()


def renew_interaction_limit(token: str, repo: str) -> str:
    """협업자만 Issue·댓글을 쓸 수 있게 제한하고 만료 시각을 돌려준다. 최대 기간이 6개월이라 매번 갱신한다."""
    resp = requests.put(
        f"{API}/repos/{repo}/interaction-limits",
        headers=_headers(token),
        json={"limit": "collaborators_only", "expiry": "six_months"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("expires_at", "")
