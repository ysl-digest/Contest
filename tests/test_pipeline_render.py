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
        today, {"linkareer": "ValueError: 구조 변경"}, deferred=2,
    )
    urgent, rest = body.split("## 📋")
    assert "wevity:1" in urgent and "D-3" in urgent and "wevity:2" not in urgent
    assert rest.index("wevity:2") < rest.index("linkareer:3")  # 마감일 미확인은 맨 뒤
    assert "주제 \\| 파이프" in body
    assert "⚠️ 확인 필요" in body and "다음 주에 발송" in body and "링커리어 수집 실패" in body
    assert "Watch → Custom → Issues" in body


def test_offline_pipeline_no_llm(http, today):
    s = Settings()
    s.request_delay = 0
    result = run(s, http, State(), today, ["wevity", "linkareer"], use_llm=False)
    keys = [c.key for c in result.contests]
    assert set(keys) == {"wevity:900001", "wevity:900002", "linkareer:800001"}
    assert not result.failures
    assert "가을 시 낭송" not in result.body and "슬로건" not in result.body
    assert result.title.endswith("(3건)")


def test_source_failure_isolated(http, today, monkeypatch):
    from contest_digest.sources import linkareer

    def boom(self):
        raise ValueError("구조 변경")

    monkeypatch.setattr(linkareer.LinkareerSource, "collect", boom)
    result = run(Settings(), http, State(), today, ["wevity", "linkareer"], use_llm=False)
    assert "linkareer" in result.failures and len(result.contests) == 2


def test_max_items_defers(http, today):
    s = Settings()
    s.max_items = 1
    result = run(s, http, State(), today, ["wevity", "linkareer"], use_llm=False)
    assert len(result.contests) == 1 and result.deferred == 2


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
