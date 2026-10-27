# Contest

IT·데이터·AI 공모전을 매주 모아 GitHub Issue 다이제스트로 발행하는 봇의 **코드 저장소**입니다.

- 구독(Issue 발행) 저장소: **[yeseo-bot/Contest-Subscribe](https://github.com/yeseo-bot/Contest-Subscribe)** ← 구독은 여기서 Watch
- 이 저장소: 수집·분류·추출 코드, 주간 워크플로, 처리 이력(`data/state.json`)

## 동작 방식
```
collect(위비티·링커리어 전체 분야) → dedupe(마감·처리 이력·소스 간 같은 제목)
  → classify(Jev 결정 모델로 IT 판정, 애매한 건만 LLM 재판정, 비IT는 이력에만 기록)
  → 이월(pending) 건 우선 + 신규 IT 건, 실행당 최대 50건
  → fetch(상세·포스터) → extract(VLM, JSON 스키마) → validate(형식·범위, 재시도/대체 모델)
  → render(마크다운) → publish(Contest-Subscribe에 Issue 생성) → data/state.json 커밋
```
설계 결정과 근거는 [SPEC.md](SPEC.md)에 있습니다.

## 설정
Settings → Secrets and variables → Actions

| 종류 | 이름 | 필수 | 설명 |
|---|---|---|---|
| Secret | `OPENROUTER_API_KEY` | ✅ | OpenRouter API 키. 없으면 VLM 없이 메타데이터만 게시 |
| Secret | `ISSUE_TOKEN` | ✅ | 발행 저장소에 Issue를 쓰는 토큰. yeseo-bot 계정의 fine-grained PAT (Repository access: `Contest-Subscribe`만, Permissions: Issues Read and write) |
| Variable | `ISSUE_REPO` | 선택 | 발행 저장소 (기본 `yeseo-bot/Contest-Subscribe`) |
| Variable | `VLM_MODEL` | 선택 | 추출 주 모델 (기본 `qwen/qwen3.7-flash`) |
| Variable | `VLM_FALLBACK_MODEL` | 선택 | 추출 대체 모델 (기본 `deepseek/deepseek-v4.1-flash`) |
| Variable | `CLASSIFIER_MODEL` | 선택 | IT 분류 결정 모델, Decisions API (기본 `typesafe/jev-1.14`) |
| Variable | `CLASSIFY_HIGH` / `CLASSIFY_LOW` | 선택 | Jev 확률 기준. high 이상 IT, low 이하 비IT, 사이는 2차 LLM (기본 0.5 / 0.3, 느슨한 초기값) |
| Variable | `CLASSIFIER_FALLBACK_MODEL` | 선택 | 애매·실패 건 2차 분류 LLM (기본 `qwen/qwen3.7-flash`) |

Settings → Actions → General → Workflow permissions는 **Read and write**여야 처리 이력을 커밋할 수 있습니다.

## 수동 실행
Actions → **weekly-digest** → Run workflow
- `dry_run` 체크(기본값): Issue를 만들지 않고 결과 마크다운을 Job Summary에 출력
- `dry_run` 해제: 실제 Issue 생성 + 처리 이력 커밋

## 로컬 실행
```bash
pip install -e ".[dev]"
pytest -q                                                # 오프라인 단위 테스트
python -m contest_digest run --dry-run --offline         # fixture로 실행
python -m contest_digest run --dry-run --no-llm          # 실제 소스, LLM 없이
python -m contest_digest -v run --dry-run --max-items 3  # 분류 판정 근거(p값)까지 로그로 확인
python -m contest_digest collect --sources wevity        # 목록 수집 결과만
python -m contest_digest check-model                     # 모델 존재·이미지 입력·JSON 출력 방식 확인
```

## 처리 이력 (`data/state.json`)
- `status`: `sent`(발송) · `skipped`(비IT·마감) · `pending`(IT지만 상한·오류로 이월)
- `pending`은 목록 정보를 함께 저장해 다음 실행에서 재분류 없이 가장 먼저 처리합니다.
- 마감 후 90일이 지난 항목은 자동으로 지웁니다.

## 수집 원칙
- 각 소스의 robots.txt를 지키고, 같은 호스트에는 요청 사이에 2초 이상 간격을 둡니다. 수집은 주 1회입니다.
- 원문 본문과 포스터는 재게시하지 않고 구조화된 요약과 원문 링크만 게시합니다.
