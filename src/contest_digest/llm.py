"""OpenRouter JSON 출력 호출 공통부.

structured outputs를 지원하는 모델은 json_schema로 강제하고, 지원하지 않는 모델은
json_object 모드 + 프롬프트에 스키마를 넣는 방식으로 대체한다. 어느 쪽이든 결과는 호출부에서 검증한다.
"""

from __future__ import annotations

import json
import logging

import requests

log = logging.getLogger(__name__)


class ModelCaps:
    """/models 응답을 한 번 받아 모델별 supported_parameters를 캐시한다."""

    def __init__(self, base_url: str, data: dict[str, set[str]] | None = None):
        self.base_url = base_url
        self._data = data

    def _load(self) -> dict[str, set[str]]:
        if self._data is None:
            try:
                rows = requests.get(f"{self.base_url}/models", timeout=30).json()["data"]
                self._data = {m["id"]: set(m.get("supported_parameters", [])) for m in rows}
            except Exception as exc:  # noqa: BLE001 - 모르면 json_schema를 시도한다
                log.warning("모델 목록 조회 실패: %s", exc)
                self._data = {}
        return self._data

    def structured(self, model: str) -> bool:
        params = self._load().get(model)
        return params is None or "structured_outputs" in params


def chat_json(client, model: str, messages: list[dict], schema: dict, caps: ModelCaps) -> dict:
    if caps.structured(model):
        kwargs = {
            "response_format": {"type": "json_schema", "json_schema": schema},
            "extra_body": {"provider": {"require_parameters": True}},
        }
    else:
        hint = "다음 JSON 스키마를 따르는 JSON 객체 하나만 출력하세요:\n" + json.dumps(schema["schema"], ensure_ascii=False)
        messages = [{"role": "system", "content": hint}, *messages]
        kwargs = {"response_format": {"type": "json_object"}}
    resp = client.chat.completions.create(model=model, messages=messages, temperature=0, **kwargs)
    raw = (resp.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    return json.loads(raw)
