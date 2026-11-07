import pytest

from aipulse.fetchers import clickpy


@pytest.fixture
def captured_queries(monkeypatch):
    queries: list[str] = []

    def _fake_run_query(sql: str) -> dict:
        queries.append(sql)
        if sql.startswith("DESCRIBE"):
            return {"data": [{"name": c} for c in clickpy._REQUIRED_COLUMNS]}
        return {"data": []}

    monkeypatch.setattr(clickpy, "_run_query", _fake_run_query)
    return queries


def _data_queries(queries: list[str]) -> list[str]:
    return [q for q in queries if not q.startswith("DESCRIBE")]


def test_fetch_country_downloads_excludes_unattributed_rows(captured_queries):
    clickpy.fetch_country_downloads()
    data_queries = _data_queries(captured_queries)
    assert data_queries
    assert all("country_code != ''" in q for q in data_queries)


def test_fetch_country_downloads_by_day_excludes_unattributed_rows(captured_queries):
    clickpy.fetch_country_downloads_by_day("2026-10-01", "2026-10-31")
    data_queries = _data_queries(captured_queries)
    assert data_queries
    assert all("country_code != ''" in q for q in data_queries)
