# Contest

공모전을 매주 모아 IT·Non-IT로 나눠 GitHub Issue 다이제스트로 발행하는 봇의 **코드 저장소**입니다.

- IT·데이터·AI 공모전 구독: **[yeseo-bot/Contest-Subscribe](https://github.com/yeseo-bot/Contest-Subscribe)** ← Watch
- 그 외 분야 공모전 구독: **[yeseo-bot/Contest-Subscribe-Non-IT](https://github.com/yeseo-bot/Contest-Subscribe-Non-IT)** ← Watch
- 이 저장소: 수집·분류·추출 코드, 주간 워크플로, 처리 이력(`data/state.json`)

## 동작 방식
```
[classify job]  collect(위비티·링커리어 전체 분야) → dedupe(마감·처리 이력·소스 간 같은 제목)
                → classify(Jev 결정 모델로 IT 판정, 애매한 건만 LLM 재판정)
                → 신규 건을 트랙(IT/Non-IT)별 대기열(pending)에 저장 → state.json 커밋
[publish-it]    IT 대기열 마감순 최대 50건 → fetch(상세·포스터) → extract(VLM) → validate
                → render → Contest-Subscribe에 Issue → state.json 커밋
                (VLM이 비IT 분야로 판정한 건은 Non-IT 대기열로 넘김)
[publish-non-it] Non-IT 대기열로 같은 과정 → Contest-Subscribe-Non-IT에 Issue → state.json 커밋
```
트랙마다 VLM 추출이 최대 50건이라 한 job에 몰면 30분을 넘길 수 있어 job을 셋으로 나눴습니다. 순서대로 실행되고, 상태 파일은 artifact로 다음 job에 넘깁니다. IT 발행이 실패해도 Non-IT 발행은 진행합니다.
설계 결정과 근거는 [SPEC.md](SPEC.md)에 있습니다.

## 설정
Settings → Secrets and variables → Actions

| 종류 | 이름 | 필수 | 설명 |
|---|---|---|---|
| Secret | `OPENROUTER_API_KEY` | ✅ | OpenRouter API 키. 없으면 VLM 없이 메타데이터만 게시 |
| Secret | `ISSUE_TOKEN` | ✅ | 발행 저장소용 fine-grained PAT (Resource owner: `yeseo-bot`, Repository access: `Contest-Subscribe`, `Contest-Subscribe-Non-IT`). Permissions: **Issues: Read and write**(발행·잠금), **Administration: Read and write**(상호작용 제한 갱신) |
| Variable | `ISSUE_REPO` | 선택 | IT 발행 저장소 (기본 `yeseo-bot/Contest-Subscribe`) |
| Variable | `NON_IT_ISSUE_REPO` | 선택 | Non-IT 발행 저장소 (기본 `yeseo-bot/Contest-Subscribe-Non-IT`) |
| Variable | `VLM_MODEL` | 선택 | 추출 주 모델 (기본 `qwen/qwen3.7-flash`) |
| Variable | `VLM_FALLBACK_MODEL` | 선택 | 추출 대체 모델 (기본 `deepseek/deepseek-v4.1-flash`) |
| Variable | `CLASSIFIER_MODEL` | 선택 | IT 분류 결정 모델, Decisions API (기본 `typesafe/jev-1.14`) |
| Variable | `CLASSIFY_HIGH` / `CLASSIFY_LOW` | 선택 | Jev 확률 기준. high 이상 IT, low 이하 비IT, 사이는 2차 LLM (기본 0.5 / 0.3, 느슨한 초기값) |
| Variable | `CLASSIFIER_FALLBACK_MODEL` | 선택 | 애매·실패 건 2차 분류 LLM (기본 `qwen/qwen3.7-flash`) |

Settings → Actions → General → Workflow permissions는 **Read and write**여야 처리 이력을 커밋할 수 있습니다.

## 수동 실행
Actions → **weekly-digest** → Run workflow
- `dry_run` 체크(기본값): Issue를 만들지 않고 트랙별 결과 마크다운을 각 job의 Summary에 출력
- `dry_run` 해제: 실제 Issue 생성 + 처리 이력 커밋

## 로컬 실행
```bash
pip install -e ".[dev]"
pytest -q                                                # 오프라인 단위 테스트
python -m contest_digest run --dry-run --offline         # fixture로 실행 (분류 + IT·Non-IT 둘 다)
python -m contest_digest classify                        # 수집·분류만 하고 대기열 저장
python -m contest_digest run --track it --no-classify    # 저장된 IT 대기열만 처리·발행
python -m contest_digest run --dry-run --no-llm          # 실제 소스, LLM 없이
python -m contest_digest -v run --dry-run --max-items 3  # 분류 판정 근거(p값)까지 로그로 확인
python -m contest_digest collect --sources wevity        # 목록 수집 결과만
python -m contest_digest check-model                     # 모델 존재·이미지 입력·JSON 출력 방식 확인
```

## 구독자 메일 오염 방지
- 두 발행 저장소 모두 **상호작용 제한(협업자만)**이 걸려 있어 외부인이 Issue·댓글을 쓸 수 없습니다. 최대 6개월짜리 설정이라 실제 발행 실행 때마다 6개월로 갱신합니다.
- 발행한 Issue는 바로 잠가서(lock) 댓글을 막습니다.
- 갱신이나 잠금에 실패하면 발행은 계속하고 로그에 경고만 남깁니다. 토큰 권한을 확인하세요.

## 처리 이력 (`data/state.json`)
- `status`: `sent`(발송) · `skipped`(마감) · `pending`(분류 끝, 발행 대기·상한·오류로 이월)
- `it`: 트랙. `true`면 IT, `false`면 Non-IT
- `pending`은 목록 정보를 함께 저장해 다음 실행에서 재분류 없이 마감순으로 처리합니다.
- 마감 후 90일이 지난 항목은 자동으로 지웁니다.

## 수집 원칙
- 각 소스의 robots.txt를 지키고, 같은 호스트에는 요청 사이에 2초 이상 간격을 둡니다. 수집은 주 1회입니다.
- 원문 본문과 포스터는 재게시하지 않고 구조화된 요약과 원문 링크만 게시합니다.
