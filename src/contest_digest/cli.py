"""명령행 진입점: collect / classify / run / check-model."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import TRACKS, Settings, today_kst
from .http import HttpClient
from .offline import FixtureHttp
from .pipeline import classify_new, collect, process, save_marks
from .publish import create_issue, lock_issue, renew_interaction_limit
from .sources import SOURCES
from .state import State


def _http(args, settings: Settings):
    if args.offline:
        return FixtureHttp()
    return HttpClient(settings.user_agent, delay=settings.request_delay)


def cmd_collect(args, settings: Settings) -> int:
    listings, failures = collect(_http(args, settings), settings, args.sources)
    for it in listings:
        print(json.dumps({**it.__dict__, "apply_end": str(it.apply_end)}, ensure_ascii=False))
    for name, err in failures.items():
        print(f"[실패] {name}: {err}", file=sys.stderr)
    return 1 if failures and not listings else 0


def _use_llm(args, settings: Settings) -> bool:
    if args.no_llm:
        return False
    if not settings.openrouter_api_key:
        logging.warning("OPENROUTER_API_KEY 없음 → LLM 없이 키워드 분류·메타데이터만 사용")
        return False
    return True


def _classify(args, settings: Settings, http, state: State, today, use_llm: bool) -> bool:
    """수집·분류해 신규 건을 트랙별 pending으로 넣는다. 모든 소스가 실패하면 False."""
    cr = classify_new(settings, http, state, today, args.sources, use_llm=use_llm)
    if args.verbose:
        for key, v in cr.verdicts.items():
            logging.debug("분류 %s %s %s (%s, %s)", "IT    " if v.is_it else "Non-IT", key,
                          cr.titles.get(key, "")[:40], v.reason, v.by)
    if len(cr.failures) == len(args.sources):
        logging.error("모든 소스 수집 실패")
        return False
    return True


def _publish(settings: Settings, result) -> int | None:
    repo = settings.repo_for(result.track)
    issue = None
    if result.contests:
        issue = create_issue(settings.github_token, repo, result.title, result.body, [settings.issue_label])
        logging.info("[%s] %s Issue #%d 생성", result.track, repo, issue)
        try:
            lock_issue(settings.github_token, repo, issue)
        except Exception as exc:  # noqa: BLE001 - 이미 발행됐으므로 상태 저장은 계속한다
            logging.warning("Issue #%d 잠금 실패: %s", issue, exc)
    else:
        logging.info("[%s] 신규 0건: Issue 생성 생략", result.track)
    try:
        expires = renew_interaction_limit(settings.github_token, repo)
        logging.info("%s 상호작용 제한(협업자만) 갱신, 만료 %s", repo, expires)
    except Exception as exc:  # noqa: BLE001 - 토큰에 Administration 권한이 없으면 실패
        logging.warning("%s 상호작용 제한 갱신 실패 (ISSUE_TOKEN에 Administration 쓰기 권한 필요): %s", repo, exc)
    return issue


def _save(state: State, settings: Settings, today) -> None:
    state.prune(today, settings.state_retention_days)
    state.save(settings.state_path, today)


def cmd_classify(args, settings: Settings) -> int:
    """수집·분류만 하고 상태를 저장한다. 발행은 트랙별 run --no-classify가 맡는다."""
    today = today_kst().date()
    state = State.load(settings.state_path)
    if not _classify(args, settings, _http(args, settings), state, today, _use_llm(args, settings)):
        return 1
    _save(state, settings, today)
    return 0


def cmd_run(args, settings: Settings) -> int:
    if args.max_items is not None:
        settings.max_items = args.max_items
    use_llm = _use_llm(args, settings)
    today = today_kst().date()
    state = State.load(settings.state_path)
    http = _http(args, settings)
    if not args.no_classify and not _classify(args, settings, http, state, today, use_llm):
        if not args.dry_run:
            return 1

    tracks = list(TRACKS) if args.track == "all" else [args.track]
    for track in tracks:
        result = process(settings, http, state, today, track, use_llm=use_llm)
        if args.dry_run:
            print(f"# {result.title}\n")
            print(result.body)
            print()
            logging.info("dry-run [%s]: 발송 대상 %d건, 이월 %d건, 트랙 이동 %d건",
                         track, len(result.contests), result.deferred, result.moved)
            continue
        issue = _publish(settings, result)
        save_marks(state, result, today, issue)
    if args.dry_run:
        logging.info("dry-run: Issue 생성·상태 저장 생략")
        return 0
    _save(state, settings, today)
    return 0


def cmd_check_model(args, settings: Settings) -> int:
    """설정된 모델의 존재 여부, 이미지 입력, JSON 출력 방식을 확인한다."""
    import requests

    data = requests.get(f"{settings.openrouter_base_url}/models", timeout=30).json()["data"]
    by_id = {m["id"]: m for m in data}
    ok = True
    roles = [("VLM", settings.vlm_model, True), ("VLM 대체", settings.vlm_fallback_model, True),
             ("분류 대체", settings.classifier_fallback_model, False)]
    for role, model, need_image in roles:
        m = by_id.get(model)
        if not m:
            print(f"✗ [{role}] {model}: 모델 없음")
            ok = False
            continue
        image = "image" in m.get("architecture", {}).get("input_modalities", [])
        so = "structured_outputs" in m.get("supported_parameters", [])
        price = m.get("pricing", {})
        usable = image or not need_image
        mode = "json_schema" if so else "json_object 대체"
        print(f"{'✓' if usable else '✗'} [{role}] {model}: image={image} 출력={mode} "
              f"prompt=${price.get('prompt')}/tok completion=${price.get('completion')}/tok")
        ok &= usable
    # Jev 같은 결정 모델은 /models 목록에 없으므로 엔드포인트 정보로 확인한다
    model = settings.classifier_model.lstrip("~")
    resp = requests.get(f"{settings.openrouter_base_url}/models/{model}/endpoints", timeout=30)
    endpoints = resp.json().get("data", {}).get("endpoints", []) if resp.ok else []
    if endpoints:
        price = endpoints[0].get("pricing", {})
        print(f"✓ [분류] {settings.classifier_model}: Decisions API prompt=${price.get('prompt')}/tok")
    else:
        print(f"✗ [분류] {settings.classifier_model}: 엔드포인트 없음")
        ok = False
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contest_digest")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--sources", nargs="+", default=list(SOURCES), choices=list(SOURCES))
        p.add_argument("--offline", action="store_true", help="tests/fixtures HTML로 실행")

    p_collect = sub.add_parser("collect", help="목록 수집 결과를 JSON Lines로 출력")
    common(p_collect)
    p_classify = sub.add_parser("classify", help="수집·분류해 신규 건을 트랙별 대기열(pending)에 저장")
    common(p_classify)
    p_classify.add_argument("--no-llm", action="store_true", help="LLM 없이 키워드로 분류")
    p_run = sub.add_parser("run", help="(분류 후) 트랙별 추출·발행")
    common(p_run)
    p_run.add_argument("--track", choices=[*TRACKS, "all"], default="all", help="발행할 트랙 (기본 all)")
    p_run.add_argument("--no-classify", action="store_true", help="수집·분류 없이 저장된 대기열만 처리")
    p_run.add_argument("--dry-run", action="store_true", help="Issue 생성·상태 저장 없이 마크다운만 출력")
    p_run.add_argument("--no-llm", action="store_true", help="VLM 없이 메타데이터만 사용")
    p_run.add_argument("--max-items", type=int, help="트랙별 처리 상한")
    sub.add_parser("check-model", help="설정된 VLM 모델의 기능 지원 여부 확인")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    settings = Settings()
    handlers = {"collect": cmd_collect, "classify": cmd_classify, "run": cmd_run, "check-model": cmd_check_model}
    return handlers[args.cmd](args, settings)
