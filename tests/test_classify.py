import json

from contest_digest.classify import Classifier
from contest_digest.config import Settings
from contest_digest.llm import ModelCaps
from contest_digest.models import Listing
from test_extract import fake_client


def L(id, title, cats=()):
    return Listing("wevity", id, title, f"u/{id}", categories=list(cats))


def answer(*rows):
    return json.dumps({"results": [{"key": k, "is_it": v, "reason": "r"} for k, v in rows]})


def make(outputs, batch=40):
    s = Settings()
    s.classifier_model, s.classifier_fallback_model, s.classify_batch = "jev", "slm", batch
    client, comp = fake_client(outputs)
    caps = ModelCaps("unused", {"jev": {"structured_outputs"}, "slm": {"structured_outputs"}})
    return Classifier(s, client, caps), comp


def test_batches_and_verdicts():
    items = [L("1", "AI 해커톤"), L("2", "AI로 만든 숏폼 영상 공모"), L("3", "시 낭송")]
    clf, comp = make([answer(("wevity:1", True), ("wevity:2", False)), answer(("wevity:3", False))], batch=2)
    out = clf.classify(items)
    assert [out[f"wevity:{i}"].is_it for i in "123"] == [True, False, False]
    assert len(comp.requests) == 2 and comp.requests[0]["model"] == "jev"
    sent = comp.requests[0]["messages"][0]["content"]
    assert "AI 해커톤" in sent and "시 낭송" not in sent  # 배치 분할


def test_fallback_model_for_missing_keys_then_keyword():
    items = [L("1", "데이터 분석 대회"), L("2", "앱 개발 챌린지"), L("3", "사진 공모")]
    # jev는 1번만 답함 → slm 호출 실패 → 남은 건 키워드 규칙
    clf, comp = make([answer(("wevity:1", False)), RuntimeError("down")])
    out = clf.classify(items)
    assert out["wevity:1"].is_it is False and out["wevity:1"].by == "jev"
    assert out["wevity:2"].is_it is True and out["wevity:2"].by == "keyword"
    assert out["wevity:3"].is_it is False
    assert "앱 개발" in comp.requests[1]["messages"][0]["content"]
    assert "wevity:1\"" not in comp.requests[1]["messages"][0]["content"]


def test_ignores_unknown_keys():
    clf, _ = make([answer(("wevity:1", True), ("wevity:999", True))])
    assert set(clf.classify([L("1", "x")])) == {"wevity:1"}
