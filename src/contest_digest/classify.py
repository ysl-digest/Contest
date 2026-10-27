"""classify 단계: 전체 공모전 중 IT·데이터·AI 주제만 고른다.

목록 메타데이터(제목·주최·분야)만 묶어서 의사결정 모델(Jev Router)이나 SLM에 보낸다.
상세 페이지·포스터를 받기 전에 걸러서 VLM 호출과 요청 수를 줄인다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .config import Settings
from .filters import is_it_related
from .llm import ModelCaps, chat_json
from .models import Listing

log = logging.getLogger(__name__)

PROMPT = """다음 공모전 목록에서 각 항목이 IT·데이터·AI 분야인지 판정하세요.

IT로 본다: AI/머신러닝, 데이터 분석·시각화, SW·앱·웹 개발, 해커톤, 보안, 클라우드, IoT, 로봇·자율주행 SW, 디지털 서비스 기획(기술 구현이 핵심인 경우).
IT가 아니다: 슬로건·네이밍, 영상·사진·UCC, 미술·디자인(UX/UI 제외), 문학, 건축, 마케팅, 일반 창업(기술 언급 없음), 서포터즈.
"AI로 만든 영상/이미지 공모"처럼 AI 도구 사용만 요구하는 창작 공모는 IT가 아니다(is_it=false).
제목만으로 애매하면 분야 태그와 주최를 참고하고, 그래도 애매하면 false로 둡니다.

모든 key에 대해 결과를 하나씩 반환하세요. reason은 15자 이내."""

SCHEMA = {
    "name": "classification",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["key", "is_it", "reason"],
                    "properties": {"key": {"type": "string"}, "is_it": {"type": "boolean"}, "reason": {"type": "string"}},
                },
            }
        },
    },
}


@dataclass
class Verdict:
    is_it: bool
    reason: str
    by: str  # 판정한 모델 ID 또는 "keyword"


def _payload(batch: list[Listing]) -> str:
    rows = [{"key": it.key, "title": it.title, "host": it.host, "categories": it.categories} for it in batch]
    return json.dumps(rows, ensure_ascii=False)


class Classifier:
    def __init__(self, settings: Settings, client=None, caps: ModelCaps | None = None):
        self.settings = settings
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
        self.client = client
        self.caps = caps or ModelCaps(settings.openrouter_base_url)
        self.calls = 0

    def _batch(self, model: str, batch: list[Listing]) -> dict[str, Verdict]:
        self.calls += 1
        messages = [{"role": "user", "content": f"{PROMPT}\n\n[목록]\n{_payload(batch)}"}]
        data = chat_json(self.client, model, messages, SCHEMA, self.caps)
        keys = {it.key for it in batch}
        return {r["key"]: Verdict(bool(r["is_it"]), r.get("reason", ""), model)
                for r in data.get("results", []) if r.get("key") in keys}

    def classify(self, listings: list[Listing]) -> dict[str, Verdict]:
        out: dict[str, Verdict] = {}
        size = self.settings.classify_batch
        models = [self.settings.classifier_model, self.settings.classifier_fallback_model]
        for i in range(0, len(listings), size):
            batch = listings[i:i + size]
            todo = batch
            for model in models:
                try:
                    out.update(self._batch(model, todo))
                except Exception as exc:  # noqa: BLE001 - 다음 모델로 넘긴다
                    log.warning("분류 실패 (%s): %s", model, exc)
                todo = [it for it in batch if it.key not in out]
                if not todo:
                    break
            for it in todo:  # 두 모델 모두 답하지 않은 건은 키워드 규칙으로
                out[it.key] = keyword_verdict(it)
        return out


def keyword_verdict(listing: Listing) -> Verdict:
    return Verdict(is_it_related(listing), "키워드 규칙", "keyword")


def classify_by_keyword(listings: list[Listing]) -> dict[str, Verdict]:
    return {it.key: keyword_verdict(it) for it in listings}
