from datetime import date
from pathlib import Path

import pytest

from contest_digest.offline import FixtureHttp, render_fixture

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 26)


@pytest.fixture
def today() -> date:
    return TODAY


@pytest.fixture
def load():
    def _load(name: str) -> str:
        return render_fixture((FIXTURES / name).read_text(encoding="utf-8"), TODAY)

    return _load


@pytest.fixture
def http() -> FixtureHttp:
    return FixtureHttp(FIXTURES, today=TODAY)
