import json

from contest_digest.classify import Classifier, JevDecider
from contest_digest.config import Settings
from contest_digest.llm import ModelCaps
from contest_digest.models import Listing
from test_extract import fake_client


def L(id, title, cats=()):
    return Listing("wevity", id, title, f"u/{id}", categories=list(cats))


def answer(*rows):
    return json.dumps({"results": [{"key": k, "is_it": v, "reason": "r"} for k, v in rows]})


class FakeDecider:
    def __init__(self, scores):
        self.scores = scores
        self.asked = []

    def is_it(self, listing):
        self.asked.append(listing.key)
        p = self.scores[listing.key]
        if isinstance(p, Exception):
            raise p
        return p


def make(scores, outputs=(), batch=40):
    s = Settings()
    s.classifier_model, s.classifier_fallback_model, s.classify_batch = "jev", "llm", batch
    s.classify_low, s.classify_high = 0.35, 0.65
    client, comp = fake_client(list(outputs))
    caps = ModelCaps("unused", {"llm": {"structured_outputs"}})
    return Classifier(s, client, caps, FakeDecider(scores)), comp


def test_confident_scores_skip_llm():
    clf, comp = make({"wevity:1": 0.96, "wevity:2": 0.08})
    out = clf.classify([L("1", "빅데이터 경진대회"), L("2", "슬로건 공모")])
    assert out["wevity:1"].is_it and out["wevity:1"].by == "jev" and out["wevity:1"].score == 0.96
    assert not out["wevity:2"].is_it
    assert comp.requests == []  # 2차 호출 없음


def test_unsure_and_errors_go_to_llm_then_keyword():
    scores = {"wevity:1": 0.5, "wevity:2": RuntimeError("503"), "wevity:3": 0.4, "wevity:4": 0.9}
    # LLM은 1번만 답함 → 2·3번은 키워드 규칙
    clf, comp = make(scores, [answer(("wevity:1", False))])
    items = [L("1", "창업 IR"), L("2", "앱 개발 챌린지"), L("3", "사진 공모"), L("4", "AI 해커톤")]
    out = clf.classify(items)
    assert out["wevity:1"].is_it is False and out["wevity:1"].by == "llm"
    assert out["wevity:2"].is_it is True and out["wevity:2"].by == "keyword"
    assert out["wevity:3"].is_it is False and out["wevity:3"].by == "keyword"
    assert out["wevity:4"].by == "jev"
    sent = comp.requests[0]["messages"][0]["content"]
    assert "창업 IR" in sent and "AI 해커톤" not in sent


def test_llm_failure_falls_back_to_keyword():
    clf, _ = make({"wevity:1": 0.5}, [RuntimeError("down")])
    assert clf.classify([L("1", "데이터 분석 대회")])["wevity:1"].by == "keyword"


def test_jev_request_shape():
    class Session:
        def post(self, url, headers, json, timeout):
            self.url, self.body = url, json

            class R:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"answers": {"is_it": {"type": "noul", "noul": 0.81}}, "usage": {"cost": 0.00002}}

            return R()

    s = Settings()
    s.classifier_model = "typesafe/jev-1.14"
    sess = Session()
    d = JevDecider(s, sess)
    assert d.is_it(L("1", "AI 해커톤", ["과학/공학"])) == 0.81
    assert sess.url == "https://openrouter.ai/api/alpha/decisions"
    assert sess.body["model"] == "typesafe/jev-1.14"
    assert sess.body["questions"]["is_it"]["type"] == "noul"
    assert sess.body["state"]["title"] == "AI 해커톤"
    assert d.cost == 0.00002
