"""명령행 진입점: collect / run / check-model."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import Settings, today_kst
from .http import HttpClient
from .offline import FixtureHttp
from .pipeline import collect, run, save_marks
from .publish import create_issue
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


def cmd_run(args, settings: Settings) -> int:
    if args.max_items is not None:
        settings.max_items = args.max_items
    use_llm = not args.no_llm
    if use_llm and not settings.openrouter_api_key:
        logging.warning("OPENROUTER_API_KEY 없음 → VLM 없이 메타데이터만 사용")
        use_llm = False
    today = today_kst().date()
    state = State.load(settings.state_path)
    result = run(settings, _http(args, settings), state, today, args.sources, use_llm=use_llm)

    if args.dry_run:
        print(f"# {result.title}\n")
        print(result.body)
        logging.info("dry-run: Issue 생성·상태 저장 생략 (수집 %d건, 발송 대상 %d건, 비IT %d건)",
                     result.collected, len(result.contests), result.non_it)
        if args.verbose:
            for key, v in result.verdicts.items():
                logging.debug("분류 %s %s (%s, %s)", "IT " if v.is_it else "비IT", key, v.reason, v.by)
        return 0

    if len(result.failures) == len(args.sources):
        logging.error("모든 소스 수집 실패")
        return 1
    issue = None
    if result.contests:
        issue = create_issue(settings.github_token, settings.github_repo, result.title, result.body,
                             [settings.issue_label])
        logging.info("Issue #%d 생성", issue)
    else:
        logging.info("신규 0건: Issue 생성 생략")
    save_marks(state, result, today, issue)
    state.prune(today, settings.state_retention_days)
    state.save(settings.state_path, today)
    return 0


def cmd_check_model(args, settings: Settings) -> int:
    """설정된 모델의 존재 여부, 이미지 입력, JSON 출력 방식을 확인한다."""
    import requests

    data = requests.get(f"{settings.openrouter_base_url}/models", timeout=30).json()["data"]
    by_id = {m["id"]: m for m in data}
    ok = True
    roles = [("VLM", settings.vlm_model, True), ("VLM 대체", settings.vlm_fallback_model, True),
             ("분류", settings.classifier_model, False), ("분류 대체", settings.classifier_fallback_model, False)]
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
    p_run = sub.add_parser("run", help="전체 파이프라인 실행")
    common(p_run)
    p_run.add_argument("--dry-run", action="store_true", help="Issue 생성·상태 저장 없이 마크다운만 출력")
    p_run.add_argument("--no-llm", action="store_true", help="VLM 없이 메타데이터만 사용")
    p_run.add_argument("--max-items", type=int)
    sub.add_parser("check-model", help="설정된 VLM 모델의 기능 지원 여부 확인")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    settings = Settings()
    handlers = {"collect": cmd_collect, "run": cmd_run, "check-model": cmd_check_model}
    return handlers[args.cmd](args, settings)
