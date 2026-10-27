# SPEC: Contest-Event-Subscribe

### 저장소 구성 (2026-10-27 분리)
| 저장소 | 역할 |
|---|---|
| [yeseo-bot/Contest](https://github.com/yeseo-bot/Contest) | 코드, 주간 워크플로, `data/state.json` 커밋 (커밋이 매주 생겨 60일 비활성화도 여기서 방지) |
| [yeseo-bot/Contest-Subscribe-IT](https://github.com/yeseo-bot/Contest-Subscribe-IT) | Issue 발행 전용. 구독자는 여기를 Watch. 코드 커밋이 없어 구독자에게 Issue 알림만 감 |
- 다른 저장소에 Issue를 쓰려면 `GITHUB_TOKEN`으로는 안 됨 → yeseo-bot 계정의 fine-grained PAT(`ISSUE_TOKEN`, Contest-Subscribe-IT의 Issues 쓰기만)를 씀. Issue 작성자가 사람 계정(yeseo-bot)이 되므로 Watch 메일 문제(§2 GitHub 항목)도 참고 모델과 같은 조건이 됨.

IT·데이터·AI 공모전을 매주 모아 VLM으로 구조화하고, GitHub Issue 다이제스트 1건으로 올린다. 저장소를 Watch한 사람은 이 Issue를 알림 메일로 받는다.

> 표기: **[사실]** 직접 확인함 · **[추정]** 근거는 있으나 검증 안 됨 · **(미확인)** 검증 필요

---

## 1. 결정 사항

### 범위
| 항목 | 결정 |
|---|---|
| 소스 | 위비티(wevity.com), 링커리어(linkareer.com) |
| 분야 | **수집은 전체 분야**. classify 단계에서 IT·Non-IT로 나눠 각각 다른 저장소에 발행 (IT: Contest-Subscribe-IT, Non-IT: Contest-Subscribe-Non-IT, 2026-10-27 변경) |
| 대상(참가 자격) 필터 | 하지 않음. `eligibility` 필드로 표시만 함 |

### 발송
| 항목 | 결정 |
|---|---|
| 주기 | 주 1회, 월요일 09시경 KST → cron `47 23 * * 0` (UTC 일요일 23:47, 비정각) |
| Issue 단위 | 실행 1회당 다이제스트 1건. 제목은 `[공모전 주간] YYYY-MM-DD (N건)` |
| 구성 | ① 마감임박(7일 이내) ② 나머지(마감일 오름차순). 각 항목에 확인 필요 표시. 운영 메모(이월 건수·수집 실패)와 구독 안내 문구는 본문에 넣지 않음 — 수집 실패는 워크플로 로그로 확인 |
| 신규 0건 | Issue를 만들지 않음 (로그만 남김) |
| 라벨 | `digest` 1개. 분야별 라벨은 쓰지 않음 (다이제스트라서 의미가 적음) |
| 제목 | `주간 공모전 - {월}월 {n}째주 IT·AI 공모전` / `… Non-IT 공모전`. 주차는 그 주 목요일이 속한 달 기준(ISO 8601 방식) |
| 오염 방지 | 발행 저장소에 상호작용 제한(collaborators_only, 6개월)을 걸고 실제 발행 실행 때마다 갱신. 발행한 Issue는 즉시 lock (2026-10-27, 첫 설정 만료 2027-04-27) |

### VLM
| 항목 | 결정 |
|---|---|
| API | OpenRouter, `openai` SDK + `base_url=https://openrouter.ai/api/v1` |
| 모델 | `VLM_MODEL`(주, 저가), `VLM_FALLBACK_MODEL`(대체). 둘 다 환경변수/설정값이며 기본값만 config에 둠 |
| 구조화 | `response_format={"type":"json_schema", strict}` + `provider.require_parameters=true` |
| 이미지 | 러너에서 다운로드(Referer 포함) → 최대 변 1568px로 리사이즈 → JPEG base64 data URL |
| 포스터 | 최대 2장. 없으면 텍스트만으로 추출 |
| 상한 | 실행당 VLM 대상 최대 50건. 넘치는 건은 `pending`으로 목록 정보와 함께 저장 → 다음 실행에서 재분류 없이 최우선 처리 (2026-10-27 변경) |
| 재시도 | 검증 실패 시 같은 모델로 1회 재시도 → 실패하면 대체 모델 1회 → 그래도 실패하면 `needs_review=true` |

### 추출 스키마 (확정)
```
title: str                 host: str|null           category: str|null
topic: str|null (1~2문장)   apply_start: date|null   apply_end: date|null
other_dates: [{label: str, date: date|null, note: str|null}]
prize_total: str|null      prize_details: [str]
eligibility: str|null      team_size: str|null      submission: str|null
source_url: str            poster_urls: [str]
needs_review: bool         review_reasons: [str]
```
- 날짜 형식은 `YYYY-MM-DD`. 범위를 벗어나거나(`apply_end < apply_start` 등) 형식이 틀리면 검증 실패로 처리
- 원문에 없는 정보는 null. 프롬프트에 "추측 금지"를 명시함
- `source_url`과 `poster_urls`는 VLM 출력이 아니라 수집 데이터로 덮어씀 (환각 방지)
- 마감일은 목록 메타데이터를 우선하고, VLM 값과 다르면 `review_reasons`에 기록

### 상태·운영
| 항목 | 결정 |
|---|---|
| 상태 | `data/state.json`을 코드 저장소 main에 커밋. 키는 `{source}:{id}`, 값은 `title`·`first_seen`·`apply_end`·`it`·`status`(sent/skipped/pending)·`issue` |
| 정리 | 마감 후 90일 지난 항목은 상태에서 삭제 |
| 재알림 | 하지 않음 (마감 연장·내용 수정 모두) |
| 실패 알림 | 워크플로 실패는 GitHub 기본 메일로 받음. 소스 하나가 실패하면 로그에 경고를 남기고 나머지는 계속 진행 |
| 지연 | 같은 호스트에 요청 간 2초 이상 간격, 타임아웃 20초, 재시도 2회(백오프) |
| User-Agent | 프로젝트명과 저장소 URL을 명시 |

### 품질·테스트
- 소스별 HTML fixture로 파서 단위 테스트
- extract 테스트는 OpenAI 클라이언트를 mock
- render 스냅샷 테스트
- 정답 JSON 5건: `tests/golden/`, `scripts/eval_golden.py`로 수동 평가 (CI 제외)

---

### classify 단계 (2026-10-27 추가·개정)
| 항목 | 결정 |
|---|---|
| 위치 | dedupe 뒤, fetch 앞. 상세 페이지·포스터를 받기 전에 걸러 요청 수와 VLM 비용을 줄임 |
| 입력 | 목록 메타데이터(제목·주최·분야 태그)만 |
| 1차 | `typesafe/jev-1.14` (TypeSafe Jev 결정 모델). OpenRouter `/api/alpha/decisions`에 건별 `noul`(yes/no) 질문 → IT일 확률. p≥0.5면 IT, p≤0.3면 비IT (초기 느슨한 기준, 운영하며 `CLASSIFY_HIGH/LOW` 변수로 상향) |
| 2차 | 0.3<p<0.5(애매)이거나 Jev 호출이 실패한 건만 `qwen/qwen3.7-flash`에 40건씩 배치로 다시 판정 |
| 3차 | 2차에서도 답이 없으면 키워드 규칙 |
| 기준 | AI·데이터·SW개발·해커톤·보안·디지털 서비스 기획은 IT. AI 도구로 만드는 영상·이미지 창작 공모는 비IT |
| 기록 | 분류 결과는 `state.json`의 `it`에 남겨 재분류하지 않음. IT 트랙에서 VLM이 비IT 분야 category를 고르면 Non-IT 트랙으로 넘김(반대 방향은 없음) |
| 실행 | classify → publish-it → publish-non-it 세 job을 순서대로. 트랙별 VLM 상한 50건이라 job별 timeout을 둠 |
| 중복 | 정규화 제목(괄호 부연·기호 제거)이 같으면 소스가 달라도 1건만 발송 |
| JSON 출력 | 모델이 structured outputs를 지원하면 json_schema, 아니면 json_object + 프롬프트 스키마 (`qwen/qwen3.7-flash`가 여기에 해당 [사실: /models 조회]) |

**모델 선택 근거 [사실: 2026-10-27 실측]**
- `typesafe/jev-router`는 분류기가 아니라 **요청마다 다른 LLM을 골라 주는 라우터**임. 짧은 yes/no 질문 하나를 `anthropic/claude-sonnet-5.5`로 보냄 → 단순 분류에 비해 과한 비용.
- `typesafe/jev-latest`라는 ID는 없음. `~typesafe/jev-latest`(최신 Jev로 리다이렉트)와 `typesafe/jev-1.14`는 chat/completions가 아닌 Decisions API 전용 모델.
- Jev 1.14 샘플 7건: 빅데이터 0.96 · 보안 0.96 · AI 아이디어 0.85 · 모바일신분증 0.83 / AI 도구 영상 0.08 · 슬로건 0.08 / 창업 IR 0.50(애매 → 2차). 건당 약 $0.00002, 약 0.5초.
- `~typesafe/jev-latest` 대신 버전을 고정(`jev-1.14`)한 이유: 모델이 바뀌면 판정 기준이 몰래 달라지기 때문. 버전 올리기는 `CLASSIFIER_MODEL` 변수로 함.

## 2. 조사 결과 (근거)

### 소스 robots.txt (2026-10-27 확인)
- **위비티 [사실]**: `User-agent: * Allow: /` (GPTBot만 Crawl-delay 3).
- 위비티 목록 페이지는 정적 HTML이고 상세 링크가 `ix=` 파라미터로 노출됨 **[사실]**.
- **링커리어 [사실]**: `Allow: /`. Disallow는 `/stem/learn/*` 경로뿐이며 `/list/contest`와 `/activity/{id}`는 허용됨.
- 링커리어 목록 HTML에 `__NEXT_DATA__`/Apollo 상태가 들어 있고 `/activity/{id}` 링크가 있음 **[사실]**. 따라서 Playwright 없이 내장 JSON을 파싱함 (Playwright는 쓰지 않음).
- `api.linkareer.com` 내부 API는 쓰지 않음. 별도 robots가 없고 비공개 API라서임.
- **이용약관**: 두 사이트 모두 무단 수집·복제를 금지하는 조항이 있을 가능성이 있음 **(미확인)**. 대응: 공개 메타데이터와 요약만 게시하고, 원문 본문은 재게시하지 않고 링크만 걸며, 포스터도 링크만 걸고, 주 1회 저빈도로 수집함. **운영 전 약관 원문 확인이 필요함.**

### GitHub
- **60일 비활성 [사실]**: 공개 저장소에서 60일간 저장소 활동이 없으면 scheduled workflow가 자동 비활성화됨 (GitHub Docs).
- **상태 커밋이 비활성화를 막는지 (미확인)**: 주간 커밋이 생기므로 막힐 것으로 **[추정]**. 다만 GITHUB_TOKEN으로 한 커밋이 "활동"으로 집계되는지는 공식 문서에서 확인하지 못함. 신규 0건인 주에는 커밋이 없으므로 `last_run` 필드를 갱신해 매주 커밋함.
- **GITHUB_TOKEN으로 만든 Issue가 Watch 메일을 보내는지 (미확인)**: 공식 문서를 찾지 못했음. 참고 모델(Dev-Event-Subscribe)의 Issue 작성자는 사람 계정이라 **PAT를 쓰는 것으로 추정 [사실: 작성자 로그인 확인]**.
  → 결정: 토큰은 `ISSUE_TOKEN` 시크릿이 있으면 그것을 쓰고, 없으면 `GITHUB_TOKEN`을 씀. 첫 배포 때 실제 메일 수신을 테스트해서 이 문서를 갱신함.
- **cron [사실]**: UTC 기준이며 부하가 높으면 지연되거나 누락될 수 있음 → 비정각 47분으로 설정.

### OpenRouter [사실]
- Structured outputs 지원은 모델이 아니라 **프로바이더 엔드포인트별**로 다름.
- `require_parameters: true`를 주면 지원하는 엔드포인트로만 라우팅됨.
- 모델별 지원 여부는 `/api/v1/models`의 `supported_parameters`(`structured_outputs`, `response_format`)와 `architecture.input_modalities`(`image`)로 확인함 → `contest_digest check-model` 명령으로 실행 전에 검증.
- 기본 모델 **[사실: 2026-10-27 `/models` 조회]**: 추출 주 `qwen/qwen3.7-flash`(structured outputs 미지원 → json_object 대체), 대체 `deepseek/deepseek-v4.1-flash`. 둘 다 image 입력 지원. 실제 추출 품질은 **(미확인)** 이며 정답 JSON 평가로 확인 예정.

### 레퍼런스 사용
구조와 아이디어만 참고했고 코드는 복사하지 않았으므로 라이선스상 문제는 없음.

---

### 소스 카테고리 [사실]
- 위비티: `cidx` 20=웹/모바일/IT, 21=게임/소프트웨어, 22=과학/공학 (참고용. 현재는 전체 목록을 수집함). 위비티는 분야 태그를 넓게 다는 편(슬로건 공모에도 IT 태그가 붙음)이라 제목 키워드 필터를 함께 씀.
- 링커리어 공모전 카테고리: 28 기획/아이디어 · 29 광고/마케팅 · 30 사진/영상/UCC · 31 디자인 · 32 네이밍/슬로건 · 33 캐릭터/만화/게임 · 34 건축 · 35 과학/공학 · 36 예체능/패션 · 37 전시/페스티벌 · 38 문학/시나리오 · 39 해외 · 40 학술 · 41 창업 · 42 기타. **IT 전용 카테고리가 없음** → 35 필터 목록과 전체 목록을 함께 수집하고 제목 키워드로 거름.
- 키워드 필터를 통과한 비IT 건은 VLM이 `category="비IT"`로 판정하면 발송에서 제외함.

## 3. 미확인 / 운영 전 확인 항목
1. 위비티·링커리어 이용약관상 수집 허용 범위
2. GITHUB_TOKEN으로 만든 Issue의 Watch 메일 발송 여부 (첫 실행 때 테스트하고, 안 되면 PAT 또는 GitHub App 사용)
3. bot 커밋이 60일 비활성 판정에서 활동으로 인정되는지
4. Jev 판정 품질 (샘플 7건만 확인함). 첫 몇 주는 `-v` 로그의 판정 근거(p값)를 보고 임계값(0.3/0.5)을 조정할 필요가 있음. Decisions API는 alpha 단계라 사양이 바뀔 수 있음 (미확인)
5. 링커리어 `__NEXT_DATA__` 스키마의 안정성 (깨지면 소스 실패로 보고)
6. Issue 생성 시 없는 라벨(`digest`)이 자동으로 만들어지는지 (미확인. 안 되면 라벨을 수동으로 생성)

---

## 4. 구조 (pasted §7 대비 변경)
- `src/contest_digest/{fetch.py,validate.py,filters.py}` 추가
- `cli.py`에 `check-model` 추가
- `scripts/eval_golden.py`, `tests/golden/` 추가
- 워크플로 권한: `issues: write`, `contents: write`. `concurrency` 그룹으로 중복 실행 방지. `workflow_dispatch` 입력은 `dry_run`(bool)·`max_items`
