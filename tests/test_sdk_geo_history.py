import pytest

from aipulse import history_rollup, notify, publish
from aipulse.errors import SourceFetchError
from aipulse.fetchers import clickpy
from aipulse.pipeline import run_sdk_geo_history_rollup, run_sdk_geo_trend
from aipulse.sdk_geo_trend import compute_sdk_geo_trend


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(publish, "DATA_DIR", data_dir)
    monkeypatch.setattr(publish, "LATEST_DIR", data_dir / "latest")
    monkeypatch.setattr(publish, "MANIFEST_PATH", data_dir / "manifest.json")
    monkeypatch.setattr(history_rollup, "LATEST_DIR", data_dir / "latest")
    monkeypatch.setattr(notify, "notify", lambda *a, **k: None)
    return data_dir


# --- compute_sdk_geo_trend -----------------------------------------------


def test_compute_sdk_geo_trend_aggregates_by_region_and_package():
    rows = [
        {"date": "2026-07-01", "package": "anthropic", "country_code": "US", "downloads": 100},
        {"date": "2026-07-01", "package": "anthropic", "country_code": "CA", "downloads": 20},
        {"date": "2026-07-01", "package": "anthropic", "country_code": "DE", "downloads": 30},
        {"date": "2026-07-01", "package": "openai", "country_code": "US", "downloads": 50},
    ]
    trend = compute_sdk_geo_trend(rows, "2026-07-18T00:00:00+00:00")

    series = {(r["date"], r["region"], r["package"]): r["downloads"] for r in trend["series"]}
    assert series[("2026-07-01", "North America", "anthropic")] == 120  # US + CA
    assert series[("2026-07-01", "Europe", "anthropic")] == 30
    assert series[("2026-07-01", "North America", "openai")] == 50
    assert "regions" in trend and "packages" in trend


def test_compute_sdk_geo_trend_skips_unclassified_country_codes():
    rows = [
        {"date": "2026-07-01", "package": "anthropic", "country_code": "AU", "downloads": 100},  # no Oceania bucket
    ]
    trend = compute_sdk_geo_trend(rows, "2026-07-18T00:00:00+00:00")
    assert trend["series"] == []


def test_compute_sdk_geo_trend_empty_rollup_produces_empty_series():
    trend = compute_sdk_geo_trend([], "2026-07-18T00:00:00+00:00")
    assert trend["series"] == []


# --- run_sdk_geo_history_rollup -------------------------------------------


def test_run_sdk_geo_history_rollup_merges_fetched_window(monkeypatch):
    monkeypatch.setattr(
        clickpy,
        "fetch_country_downloads_by_day",
        lambda start, end: {
            "anthropic": [{"date": "2026-07-17", "country_code": "US", "downloads": 100}],
            "openai": [{"date": "2026-07-17", "country_code": "DE", "downloads": 50}],
        },
    )
    status = run_sdk_geo_history_rollup("2026-07-18")
    assert status["status"] == "ok"

    rows = history_rollup.load_rollup("sdk_geo")["rows"]
    assert len(rows) == 2
    assert {r["package"] for r in rows} == {"anthropic", "openai"}
    assert all(r["source"] == "pipeline" for r in rows)


def test_run_sdk_geo_history_rollup_degrades_on_empty_response(monkeypatch):
    monkeypatch.setattr(
        clickpy,
        "fetch_country_downloads_by_day",
        lambda start, end: {"anthropic": [], "openai": []},
    )
    status = run_sdk_geo_history_rollup("2026-07-18")
    assert status["status"] == "degraded"


def test_run_sdk_geo_history_rollup_degrades_on_fetch_error(monkeypatch):
    def _raise(start, end):
        raise SourceFetchError("ClickPy unreachable")

    monkeypatch.setattr(clickpy, "fetch_country_downloads_by_day", _raise)
    status = run_sdk_geo_history_rollup("2026-07-18")
    assert status["status"] == "degraded"
    assert status["last_success"] is None


# --- run_sdk_geo_trend -----------------------------------------------------


def test_run_sdk_geo_trend_publishes_from_existing_rollup(_isolate):
    history_rollup.save_rollup(
        "sdk_geo",
        [{"date": "2026-07-17", "package": "anthropic", "country_code": "US", "downloads": 100, "source": "pipeline"}],
    )
    status = run_sdk_geo_trend("2026-07-18")
    assert status["status"] == "ok"

    published = publish.load_previous("sdk_geo_trend")
    assert published["series"][0]["region"] == "North America"


def test_run_sdk_geo_trend_ok_with_no_rollup_yet():
    status = run_sdk_geo_trend("2026-07-18")
    assert status["status"] == "ok"
    published = publish.load_previous("sdk_geo_trend")
    assert published["series"] == []
