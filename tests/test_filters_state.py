from datetime import date, timedelta

from contest_digest.filters import is_it_related, select_new
from contest_digest.models import Listing
from contest_digest.state import State


def L(id, title, cats=(), end=None, source="wevity"):
    return Listing(source=source, id=id, title=title, url=f"u/{id}", apply_end=end, categories=list(cats))


def test_it_keywords():
    assert is_it_related(L("1", "AI공모전 2026"))
    assert is_it_related(L("2", "공공 데이터 활용 경진대회"))
    assert not is_it_related(L("3", "International Short Film Competition"))  # 'it' 부분 문자열 오탐 방지
    assert not is_it_related(L("4", "슬로건 공모", ["기획/아이디어", "웹/모바일/IT"]))
    assert is_it_related(L("5", "스마트시티 서비스 공모", ["웹/모바일/IT", "게임/소프트웨어"]))
    assert not is_it_related(L("6", "무언가 공모", ["기타"]))


def test_select_new(today):
    items = [
        L("1", "AI 해커톤", end=today + timedelta(days=9)),
        L("2", "AI 해커톤 지난것", end=today - timedelta(days=1)),
        L("3", "데이터 분석", end=today + timedelta(days=2)),
        L("4", "앱 개발", end=None),
        L("1", "AI 해커톤 중복", end=today),
    ]
    got = select_new(items, seen={"wevity:4"}, today=today)
    assert [g.id for g in got] == ["3", "1"]  # 마감순, 마감·기처리·중복 제외


def test_state_roundtrip_and_prune(tmp_path, today):
    path = tmp_path / "state.json"
    s = State()
    s.mark("wevity:1", today, today + timedelta(days=3), 10)
    s.mark("wevity:old", today - timedelta(days=200), date(2026, 1, 1), 1)
    s.mark("linkareer:x", today - timedelta(days=200), None, None)
    s.prune(today, 90)
    s.save(path, today)
    loaded = State.load(path)
    assert loaded.seen() == {"wevity:1"}
    assert loaded.last_run == today.isoformat()
    assert loaded.items["wevity:1"]["issue"] == 10


def test_state_missing_file(tmp_path):
    assert State.load(tmp_path / "nope.json").seen() == set()


def test_cross_source_title_dedupe(today):
    from contest_digest.filters import title_key

    a = L("1", "2026 DATA·AI 분석 경진대회", end=today, source="wevity")
    b = L("2", "[KISTI] 2026 DATA·AI 분석 경진대회", end=today, source="linkareer")
    c = L("3", "2026 데이터 분석 경진대회", end=today)
    assert title_key(a.title) == title_key(b.title)
    got = select_new([a, b, c], set(), today)
    assert len(got) == 2 and {g.title for g in got} >= {"2026 데이터 분석 경진대회"}
    # 지난 실행에서 보낸 제목도 제외
    assert select_new([b], set(), today, seen_titles={title_key(a.title)}) == []
