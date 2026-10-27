import json
from datetime import timedelta
from types import SimpleNamespace

from contest_digest.config import Settings
from contest_digest.extract import Extractor
from contest_digest.models import Detail, Listing


class FakeCompletions:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=out))])


def fake_client(outputs):
    comp = FakeCompletions(outputs)
    return SimpleNamespace(chat=SimpleNamespace(completions=comp)), comp


def good(today, **over):
    data = {
        "title": "제1회 가상 AI 데이터 분석 경진대회", "host": "가상데이터진흥원", "category": "AI/데이터",
        "topic": "공공 데이터로 생활 문제를 푸는 AI 모델 개발", "apply_start": (today - timedelta(days=10)).isoformat(),
        "apply_end": (today + timedelta(days=5)).isoformat(),
        "other_dates": [{"label": "결과 발표", "date": (today + timedelta(days=30)).isoformat(), "note": None}],
        "prize_total": "1천만원", "prize_details": ["대상 1팀 500만원"], "eligibility": "대학(원)생, 일반인",
        "team_size": "1~4인", "submission": "보고서(PDF), 소스코드",
    }
    data.update(over)
    return json.dumps(data, ensure_ascii=False)


def detail(today, posters=("https://www.wevity.com/upload/a.jpg",)):
    listing = Listing("wevity", "900001", "제1회 가상 AI 데이터 분석 경진대회", "https://www.wevity.com/?ix=900001",
                      host="가상데이터진흥원", apply_end=today + timedelta(days=5))
    return Detail(listing, "본문", list(posters), today - timedelta(days=10), today + timedelta(days=5), listing.url)


def settings():
    s = Settings()
    s.vlm_model, s.vlm_fallback_model = "main/model", "fallback/model"
    return s


def test_success_sends_schema_and_image(http, today):
    client, comp = fake_client([good(today)])
    c = Extractor(settings(), http, client).extract(detail(today), today)
    assert not c.needs_review and c.category == "AI/데이터"
    req = comp.requests[0]
    assert req["model"] == "main/model"
    assert req["response_format"]["type"] == "json_schema"
    assert req["extra_body"]["provider"]["require_parameters"] is True
    images = [p for p in req["messages"][0]["content"] if p["type"] == "image_url"]
    assert images[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert c.source_url == "https://www.wevity.com/?ix=900001"  # URL은 수집 데이터로 고정


def test_retry_then_fallback(http, today):
    bad_date = good(today, apply_end="2026/13/40")
    client, comp = fake_client([bad_date, "not json", good(today)])
    c = Extractor(settings(), http, client).extract(detail(today), today)
    assert [r["model"] for r in comp.requests] == ["main/model", "main/model", "fallback/model"]
    assert "검증에 실패" in comp.requests[1]["messages"][0]["content"][1]["text"]
    assert not c.needs_review


def test_all_fail_marks_review(http, today):
    client, _ = fake_client([RuntimeError("boom")] * 3)
    c = Extractor(settings(), http, client).extract(detail(today), today)
    assert c.needs_review and any("VLM 추출 실패" in r for r in c.review_reasons)
    assert c.title == "제1회 가상 AI 데이터 분석 경진대회" and c.apply_end == (today + timedelta(days=5)).isoformat()


def test_deadline_mismatch_prefers_metadata(http, today):
    client, _ = fake_client([good(today, apply_end=(today + timedelta(days=6)).isoformat())])
    c = Extractor(settings(), http, client).extract(detail(today), today)
    assert c.apply_end == (today + timedelta(days=5)).isoformat()
    assert c.needs_review and "마감일 불일치" in c.review_reasons[0]


def test_no_poster_is_not_review(http, today):
    client, comp = fake_client([good(today)])
    c = Extractor(settings(), http, client).extract(detail(today, posters=()), today)
    assert not c.needs_review
    assert all(p["type"] == "text" for p in comp.requests[0]["messages"][0]["content"])
