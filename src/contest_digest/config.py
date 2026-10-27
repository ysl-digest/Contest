"""설정값. 환경변수가 있으면 우선하고, 없으면 기본값을 쓴다."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[2]


def today_kst() -> datetime:
    return datetime.now(KST)


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


# API 키가 없거나 분류 모델이 모두 실패했을 때 쓰는 대체 규칙.
# IT·데이터·AI 판단용 제목 키워드. 영문은 단어 경계로, 한글은 부분 문자열로 매칭한다
IT_KEYWORDS = [
    "ai", "data", "hackathon", "sw", "software", "app", "web", "it", "ict", "iot", "llm",
    "security", "ml", "dx", "인공지능", "데이터", "해커톤", "소프트웨어", "개발", "코딩",
    "프로그래밍", "알고리즘", "앱", "웹", "디지털", "보안", "클라우드", "블록체인", "메타버스",
    "로봇", "생성형", "머신러닝", "딥러닝", "오픈소스", "아이디어톤", "자율주행", "반도체",
]

# 이 카테고리만으로 구성된 공모전은 키워드가 없어도 IT로 본다
IT_ONLY_CATEGORIES = {"웹/모바일/IT", "웹/모바일/플래시", "게임/소프트웨어", "과학/공학", "학술", "기타"}


@dataclass
class Settings:
    openrouter_api_key: str = field(default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", ""))
    openrouter_base_url: str = field(default_factory=lambda: _env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    vlm_model: str = field(default_factory=lambda: _env("VLM_MODEL", "qwen/qwen3.7-flash"))
    vlm_fallback_model: str = field(default_factory=lambda: _env("VLM_FALLBACK_MODEL", "deepseek/deepseek-v4.1-flash"))
    classifier_model: str = field(default_factory=lambda: _env("CLASSIFIER_MODEL", "typesafe/jev-1.14"))
    classifier_fallback_model: str = field(default_factory=lambda: _env("CLASSIFIER_FALLBACK_MODEL", "qwen/qwen3.7-flash"))
    # Jev 확률이 high 이상이면 IT, low 이하면 비IT, 그 사이는 2차 LLM에 다시 묻는다.
    # 초기값은 IT를 넓게 통과시키는 느슨한 기준. 품질을 보며 변수로 올린다.
    classify_low: float = field(default_factory=lambda: float(_env("CLASSIFY_LOW", "0.3")))
    classify_high: float = field(default_factory=lambda: float(_env("CLASSIFY_HIGH", "0.5")))
    classify_batch: int = field(default_factory=lambda: int(_env("CLASSIFY_BATCH", "40")))
    max_items: int = field(default_factory=lambda: int(_env("MAX_ITEMS", "40")))
    max_posters: int = field(default_factory=lambda: int(_env("MAX_POSTERS", "2")))
    max_pages: int = field(default_factory=lambda: int(_env("MAX_PAGES", "5")))
    request_delay: float = field(default_factory=lambda: float(_env("REQUEST_DELAY", "2.0")))
    urgent_days: int = 7
    state_retention_days: int = 90
    text_char_limit: int = 6000
    image_max_side: int = 1568
    user_agent: str = "Contest-Subscribe/0.1 (+https://github.com/yeseoLee/Contest-Subscribe)"
    github_token: str = field(default_factory=lambda: os.environ.get("ISSUE_TOKEN") or os.environ.get("GITHUB_TOKEN", ""))
    github_repo: str = field(default_factory=lambda: _env("GITHUB_REPOSITORY", "yeseoLee/Contest-Subscribe"))
    issue_label: str = "digest"
    state_path: Path = field(default_factory=lambda: Path(_env("STATE_PATH", str(ROOT / "data" / "state.json"))))
    prompt_path: Path = ROOT / "prompts" / "extract.md"
