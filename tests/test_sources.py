from datetime import timedelta

import pytest

from contest_digest.sources import linkareer, wevity


def test_wevity_list(load, today):
    items = wevity.parse_list(load("wevity_list.html"), today)
    assert [i.id for i in items] == ["900001", "900002", "900003"]  # 마감 건 제외
    first = items[0]
    assert first.title == "제1회 가상 AI 데이터 분석 경진대회"  # SPECIAL 배지 제거
    assert first.host == "가상데이터진흥원"
    assert first.apply_end == today + timedelta(days=5)
    assert first.categories == ["웹/모바일/IT", "과학/공학"]
    assert first.url.endswith("ix=900001")


def test_wevity_detail(load, today):
    listing = wevity.parse_list(load("wevity_list.html"), today)[0]
    d = wevity.parse_detail(load("wevity_detail.html"), listing)
    assert d.apply_start == today - timedelta(days=10)
    assert d.apply_end == today + timedelta(days=5)
    assert d.poster_urls == ["https://www.wevity.com/upload/contest/fake_poster.jpg"]
    assert "1~4인" in d.text and "alert" not in d.text


def test_linkareer_list(load, today):
    items = linkareer.parse_list(load("linkareer_list.html"))
    ids = sorted(i.id for i in items)
    assert ids == ["800001", "800002", "800003"]  # activityTypeID 3(공모전)만
    hack = next(i for i in items if i.id == "800001")
    assert hack.apply_end == today + timedelta(days=12)
    assert hack.categories == ["과학/공학"]
    assert hack.url == "https://linkareer.com/activity/800001"


def test_linkareer_detail(load, today):
    listing = next(i for i in linkareer.parse_list(load("linkareer_list.html")) if i.id == "800001")
    d = linkareer.parse_detail(load("linkareer_detail_800001.html"), listing)
    assert d.apply_start == today - timedelta(days=5)
    assert d.poster_urls == ["https://api.linkareer.com/attachments/1", "https://api.linkareer.com/attachments/2"]
    assert "1500만원" in d.text and "2~5인" in d.text


def test_linkareer_structure_change():
    with pytest.raises(ValueError, match="__NEXT_DATA__"):
        linkareer.parse_list("<html>no data</html>")
