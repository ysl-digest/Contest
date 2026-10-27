from contest_digest.config import Settings
from contest_digest.models import Contest
from contest_digest.pipeline import run
from contest_digest.render import render
from contest_digest.state import State


def C(key, end, **kw):
    return Contest(title=kw.pop("title", key), key=key, source_url=f"https://x/{key}", apply_end=end, **kw)


def test_render_sections(today):
    body = render(
        [C("wevity:2", "2026-11-20"), C("wevity:1", "2026-10-29", topic="주제 | 파이프"),
         C("linkareer:3", None, needs_review=True, review_reasons=["마감일 확인 불가"])],
        today,
    )
    urgent, rest = body.split("## 📋")
    assert "wevity:1" in urgent and "D-3" in urgent and "wevity:2" not in urgent
    assert rest.index("wevity:2") < rest.index("linkareer:3")  # 마감일 미확인은 맨 뒤
    assert "주제 \\| 파이프" in body
    assert "⚠️ 확인 필요" in body
    assert "운영 메모" not in body and "Watch" not in body and "Unwatch" not in body


def test_offline_pipeline_no_llm(http, today):
    s = Settings()
    s.request_delay = 0
    result = run(s, http, State(), today, ["wevity", "linkareer"], use_llm=False)
    keys = [c.key for c in result.contests]
    assert set(keys) == {"wevity:900001", "wevity:900002", "linkareer:800001"}
    assert not result.failures
    assert "가을 시 낭송" not in result.body and "슬로건" not in result.body
    assert result.title.startswith("주간 공모전 - ") and result.title.endswith("째주 IT 공모전")


def test_source_failure_isolated(http, today, monkeypatch):
    from contest_digest.sources import linkareer

    def boom(self):
        raise ValueError("구조 변경")

    monkeypatch.setattr(linkareer.LinkareerSource, "collect", boom)
    result = run(Settings(), http, State(), today, ["wevity", "linkareer"], use_llm=False)
    assert "linkareer" in result.failures and len(result.contests) == 2


def test_max_items_defers_to_pending_and_prioritizes_next_run(http, today, monkeypatch):
    from datetime import timedelta

    from contest_digest.pipeline import save_marks
    from contest_digest.sources import linkareer, wevity

    s = Settings()
    s.max_items = 1
    state = State()
    result = run(s, http, state, today, ["wevity", "linkareer"], use_llm=False)
    assert [c.key for c in result.contests] == ["wevity:900001"] and result.deferred == 2
    save_marks(state, result, today, issue=1)
    assert state.items["wevity:900002"]["status"] == "pending"
    assert state.items["wevity:900002"]["listing"]["url"].endswith("ix=900002")
    assert "wevity:900002" not in state.seen()

    # 다음 주: 목록에서 사라져도(수집 0건) pending은 재분류 없이 우선 처리된다
    monkeypatch.setattr(wevity.WevitySource, "collect", lambda self: [])
    monkeypatch.setattr(linkareer.LinkareerSource, "collect", lambda self: [])

    class NoClassify:
        def classify(self, listings):
            assert listings == []  # pending은 분류 대상이 아님
            return {}

    nxt = today + timedelta(days=1)
    s.max_items = 5
    r2 = run(s, http, state, nxt, ["wevity", "linkareer"], use_llm=False, classifier=NoClassify())
    assert {c.key for c in r2.contests} == {"wevity:900002", "linkareer:800001"} and r2.deferred == 0
    save_marks(state, r2, nxt, issue=2)
    assert state.items["wevity:900002"]["status"] == "sent" and "listing" not in state.items["wevity:900002"]
    assert state.items["wevity:900002"]["first_seen"] == today.isoformat()  # 최초 발견일 유지
    assert state.pending() == []


def test_expired_pending_is_dropped(today):
    from datetime import timedelta

    from contest_digest.models import Listing

    state = State()
    old = Listing("wevity", "1", "AI 대회", "u/1", apply_end=today - timedelta(days=1))
    state.mark(old.key, today, old.apply_end, None, title=old.title, is_it=True, status="pending", listing=old)
    assert state.pending()[0].apply_end == old.apply_end


def test_pipeline_with_classifier_marks_non_it(http, today, tmp_path):
    from contest_digest.classify import Verdict
    from contest_digest.pipeline import save_marks

    class FakeClassifier:
        def classify(self, listings):
            # 키워드 규칙과 달리 900002(스마트시티)를 비IT로, 800002(시 낭송)도 비IT로
            return {it.key: Verdict(it.key in {"wevity:900001", "linkareer:800001"}, "", "fake") for it in listings}

    s = Settings()
    result = run(s, http, State(), today, ["wevity", "linkareer"], use_llm=False, classifier=FakeClassifier())
    assert {c.key for c in result.contests} == {"wevity:900001", "linkareer:800001"}
    assert result.non_it == 3 and result.collected == 6

    state = State()
    save_marks(state, result, today, issue=7)
    assert state.items["wevity:900001"]["issue"] == 7 and state.items["wevity:900001"]["it"] is True
    assert state.items["wevity:900003"]["it"] is False and state.items["wevity:900003"]["issue"] is None
    assert state.items["wevity:900003"]["title"] == "우리 동네 슬로건 공모전"
    # 다음 실행에서는 모두 기처리
    again = run(s, http, state, today, ["wevity", "linkareer"], use_llm=False, classifier=FakeClassifier())
    assert again.contests == [] and again.marks == []


def test_render_other_date_period(today):
    from contest_digest.models import OtherDate

    c = C("wevity:1", "2026-11-20", other_dates=[OtherDate(label="본선", date="2026-11-05", end_date="2026-11-06"),
                                                 OtherDate(label="발표", date="2026-12-01")])
    assert "본선 2026-11-05 ~ 2026-11-06, 발표 2026-12-01" in render([c], today)


def test_title_week_of_month():
    from datetime import date

    from contest_digest.render import title, week_of_month

    assert title([], date(2026, 10, 12)) == "주간 공모전 - 10월 3째주 IT 공모전"
    assert week_of_month(date(2026, 10, 1)) == (10, 1)   # 목요일
    assert week_of_month(date(2026, 10, 26)) == (10, 5)
    assert week_of_month(date(2026, 11, 30)) == (12, 1)  # 그 주 목요일이 12월
    assert week_of_month(date(2026, 6, 1)) == (6, 1)
