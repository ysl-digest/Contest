# 정답 JSON (회귀 평가용)

포스터와 원문을 사람이 직접 보고 만든 정답 5건을 여기에 둔다. `scripts/eval_golden.py`가 실제 VLM 결과와 필드별로 비교한다 (CI 제외).

```json
{
  "source": "wevity",
  "id": "111768",
  "url": "https://www.wevity.com/?c=find&s=1&gbn=view&ix=111768",
  "title": "공모전 제목",
  "expected": {"host": "...", "apply_start": "2026-10-01", "apply_end": "2026-11-14", "prize_total": "...", "team_size": "1~4인", "category": "AI/데이터"}
}
```

- 원문이 마감되면 상세 페이지가 사라질 수 있으므로 분기마다 교체한다.
- 원문 본문은 저장하지 않는다 (정답 필드만).
