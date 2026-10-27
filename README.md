# Contest-Subscribe

IT·데이터·AI 공모전을 매주 모아 **GitHub Issue 다이제스트**로 발행합니다. 저장소를 Watch하면 GitHub 알림 메일로 받아볼 수 있습니다. 별도 메일 서버나 구독자 DB는 없습니다.

- 소스: [위비티](https://www.wevity.com), [링커리어](https://linkareer.com)
- 발송: 매주 월요일 오전 9시경 (KST)
- 내용: 공모 주제, 접수 기간, 상금, 참가 자격, 팀 구성, 제출물을 원문과 포스터에서 AI(VLM)로 요약하고 원문 링크를 함께 겁니다.

## 구독하기

1. 저장소 우측 상단 **Watch → Custom** 선택
2. **Issues** 체크 → Apply
3. [알림 설정](https://github.com/settings/notifications)에서 Watching 항목의 **Email**이 켜져 있는지 확인

**구독 취소**: **Watch → Participating and @mentions**(또는 Ignore)로 바꾸면 됩니다.

> AI 요약은 틀릴 수 있습니다. 지원 전에 반드시 원문을 확인하세요.

---

## 운영자용

### 동작 방식
```
collect(소스별 목록) → dedupe(IT 필터·마감·state.json 비교) → fetch(상세·포스터)
  → extract(OpenRouter VLM, JSON 스키마) → validate(형식·범위, 재시도/대체 모델)
  → render(마크다운) → publish(Issue 생성) → data/state.json 커밋
```
설계 결정과 근거는 [SPEC.md](SPEC.md)에 있습니다.

### 시크릿과 변수 설정
Settings → Secrets and variables → Actions

| 종류 | 이름 | 필수 | 설명 |
|---|---|---|---|
| Secret | `OPENROUTER_API_KEY` | ✅ | OpenRouter API 키. 없으면 VLM 없이 메타데이터만 게시 |
| Secret | `ISSUE_TOKEN` | 선택 | Issue 작성용 PAT(fine-grained, 이 저장소의 Issues: Read and write). 없으면 `GITHUB_TOKEN` 사용 |
| Variable | `VLM_MODEL` | 선택 | 주 모델 ID (기본 `google/gemini-2.5-flash-lite`) |
| Variable | `VLM_FALLBACK_MODEL` | 선택 | 대체 모델 ID (기본 `anthropic/claude-haiku-5.5`) |

추가로 Settings → Actions → General → Workflow permissions가 **Read and write**여야 상태 파일을 커밋할 수 있습니다.

### 수동 실행
Actions → **weekly-digest** → Run workflow
- `dry_run` 체크(기본값): Issue를 만들지 않고 결과 마크다운을 Job Summary에 출력
- `dry_run` 해제: 실제 Issue 생성 + 상태 커밋

### 로컬 실행
```bash
pip install -e ".[dev]"
pytest -q                                              # 오프라인 단위 테스트
python -m contest_digest run --dry-run --offline       # fixture로 실행
python -m contest_digest run --dry-run --no-llm        # 실제 소스, VLM 없이
OPENROUTER_API_KEY=... python -m contest_digest run --dry-run --max-items 3
python -m contest_digest collect --sources wevity      # 목록 수집 결과만
python -m contest_digest check-model                   # 모델의 이미지·structured outputs 지원 확인
```

### 수집 원칙
- 각 소스의 robots.txt를 지키고, 같은 호스트에는 요청 사이에 2초 이상 간격을 둡니다. 수집은 주 1회입니다.
- 원문 본문과 포스터는 재게시하지 않고 구조화된 요약과 원문 링크만 게시합니다.
