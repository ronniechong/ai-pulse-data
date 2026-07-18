import pytest

from aipulse import history_rollup
from aipulse.schemas import OpenRouterRankingRow


@pytest.fixture(autouse=True)
def _isolate_latest_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(history_rollup, "LATEST_DIR", tmp_path / "latest")
    return tmp_path / "latest"


def _row(date, model, total_tokens):
    return OpenRouterRankingRow(date=date, model_permaslug=model, total_tokens=total_tokens)


def test_rank_and_share_computed_per_day_independently():
    rows = [
        _row("2025-01-01", "a", 70),
        _row("2025-01-01", "b", 30),
        _row("2025-01-02", "a", 10),
        _row("2025-01-02", "b", 90),
    ]
    merged = history_rollup.merge_rankings_rows([], rows, source="backfill")
    by_date = {}
    for r in merged:
        by_date.setdefault(r["date"], []).append(r)

    day1 = {r["model"]: r for r in by_date["2025-01-01"]}
    assert day1["a"]["rank"] == 1
    assert day1["a"]["token_share"] == 0.7
    day2 = {r["model"]: r for r in by_date["2025-01-02"]}
    assert day2["b"]["rank"] == 1
    assert day2["b"]["token_share"] == 0.9


def test_all_new_rows_tagged_with_given_source():
    rows = [_row("2025-01-01", "a", 100)]
    merged = history_rollup.merge_rankings_rows([], rows, source="backfill")
    assert merged[0]["source"] == "backfill"


def test_newer_source_overwrites_older_on_conflict():
    backfill_rows = [_row("2026-07-10", "a", 100), _row("2026-07-10", "b", 50)]
    existing = history_rollup.merge_rankings_rows([], backfill_rows, source="backfill")

    # Pipeline re-fetches the same date later — should win and relabel "pipeline".
    pipeline_rows = [_row("2026-07-10", "a", 100), _row("2026-07-10", "b", 50)]
    merged = history_rollup.merge_rankings_rows(existing, pipeline_rows, source="pipeline")

    sources = {r["model"]: r["source"] for r in merged if r["date"] == "2026-07-10"}
    assert sources == {"a": "pipeline", "b": "pipeline"}


def test_merge_preserves_untouched_dates():
    backfill_rows = [_row("2025-06-01", "a", 100)]
    existing = history_rollup.merge_rankings_rows([], backfill_rows, source="backfill")

    # A later window fetch that doesn't include 2025-06-01 must not drop it.
    newer_rows = [_row("2026-07-16", "a", 100)]
    merged = history_rollup.merge_rankings_rows(existing, newer_rows, source="pipeline")

    dates = {r["date"] for r in merged}
    assert dates == {"2025-06-01", "2026-07-16"}


def test_save_and_load_rollup_round_trip(tmp_path):
    rows = [{"date": "2025-01-01", "model": "a", "rank": 1, "token_share": 0.5, "source": "backfill"}]
    history_rollup.save_rollup("rankings", rows)
    loaded = history_rollup.load_rollup("rankings")
    assert loaded["rows"] == rows
    assert loaded["generated_at"] is not None


def test_load_rollup_missing_file_returns_empty():
    loaded = history_rollup.load_rollup("rankings")
    assert loaded == {"generated_at": None, "rows": []}


def test_rollup_to_history_reshapes_into_compute_facts_contract():
    rows = [
        {"date": "2025-01-01", "model": "a", "rank": 1, "token_share": 0.7, "source": "backfill"},
        {"date": "2025-01-01", "model": "b", "rank": 2, "token_share": 0.3, "source": "backfill"},
        {"date": "2025-01-02", "model": "a", "rank": 2, "token_share": 0.2, "source": "pipeline"},
    ]
    history_rollup.save_rollup("rankings", rows)

    history = history_rollup.rollup_to_history("rankings")

    assert [d for d, _ in history] == ["2025-01-01", "2025-01-02"]
    day1_models = history[0][1]["models"]
    assert day1_models[0] == {"rank": 1, "model": "a", "token_share": 0.7}
    assert day1_models[1] == {"rank": 2, "model": "b", "token_share": 0.3}


def test_rollup_to_history_empty_when_no_rollup_file():
    assert history_rollup.rollup_to_history("rankings") == []


def test_merge_sdk_geo_rows_dedupes_by_date_package_country():
    existing = [{"date": "2025-01-01", "package": "anthropic", "country_code": "US", "downloads": 100}]
    new_rows = [
        {"date": "2025-01-01", "package": "anthropic", "country_code": "US", "downloads": 150},
        {"date": "2025-01-01", "package": "anthropic", "country_code": "GB", "downloads": 20},
    ]
    merged = history_rollup.merge_sdk_geo_rows(existing, new_rows, source="backfill")

    assert len(merged) == 2
    us_row = next(r for r in merged if r["country_code"] == "US")
    assert us_row["downloads"] == 150  # newer wins
    assert us_row["source"] == "backfill"


def test_merge_daily_totals_rows_sums_all_models_per_day():
    rows = [
        _row("2025-01-01", "a", 70),
        _row("2025-01-01", "b", 30),
        _row("2025-01-02", "a", 10),
        _row("2025-01-02", "b", 90),
    ]
    merged = history_rollup.merge_daily_totals_rows([], rows, source="backfill")
    by_date = {r["date"]: r for r in merged}

    assert by_date["2025-01-01"]["total_tokens"] == 100
    assert by_date["2025-01-02"]["total_tokens"] == 100
    assert all(r["source"] == "backfill" for r in merged)


def test_merge_daily_totals_rows_one_row_per_day_not_per_model():
    rows = [_row("2025-01-01", "a", 70), _row("2025-01-01", "b", 30), _row("2025-01-01", "c", 50)]
    merged = history_rollup.merge_daily_totals_rows([], rows, source="pipeline")
    assert len(merged) == 1
    assert merged[0]["total_tokens"] == 150


def test_merge_daily_totals_rows_newer_fetch_wins_on_date_conflict():
    existing = [{"date": "2025-01-01", "total_tokens": 999, "source": "backfill"}]
    new_rows = [_row("2025-01-01", "a", 70), _row("2025-01-01", "b", 30)]
    merged = history_rollup.merge_daily_totals_rows(existing, new_rows, source="pipeline")
    assert len(merged) == 1
    assert merged[0]["total_tokens"] == 100
    assert merged[0]["source"] == "pipeline"
