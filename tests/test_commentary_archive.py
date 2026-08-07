import json

import pytest

from aipulse import commentary_archive


@pytest.fixture(autouse=True)
def _isolate_dirs(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    latest_dir = data_dir / "latest"
    data_dir.mkdir()
    monkeypatch.setattr(commentary_archive, "DATA_DIR", data_dir)
    monkeypatch.setattr(commentary_archive, "LATEST_DIR", latest_dir)
    return data_dir, latest_dir


def _write_day(data_dir, date_str, **commentary):
    day_dir = data_dir / date_str
    day_dir.mkdir()
    (day_dir / "commentary.json").write_text(json.dumps(commentary))


def test_build_archive_index_sorts_newest_first_and_skips_non_date_dirs(_isolate_dirs):
    data_dir, _ = _isolate_dirs
    _write_day(data_dir, "2026-07-20", headline="a", summary="s", highlights=[], tone="quiet", source="template")
    _write_day(data_dir, "2026-07-22", headline="c", summary="s", highlights=[], tone="big_day", source="llm")
    _write_day(data_dir, "2026-07-21", headline="b", summary="s", highlights=[], tone="notable", source="llm")
    (data_dir / "latest").mkdir()  # non-date dir, no commentary.json anyway

    entries = commentary_archive.build_archive_index()

    assert [e["date"] for e in entries] == ["2026-07-22", "2026-07-21", "2026-07-20"]
    assert entries[0]["headline"] == "c"


def test_build_archive_index_skips_days_with_no_commentary(_isolate_dirs):
    data_dir, _ = _isolate_dirs
    (data_dir / "2026-07-19").mkdir()  # e.g. facts/commentary was skipped that day
    _write_day(data_dir, "2026-07-20", headline="a", summary="s", highlights=[], tone="quiet", source="template")

    entries = commentary_archive.build_archive_index()

    assert [e["date"] for e in entries] == ["2026-07-20"]


def test_build_archive_index_handles_missing_source_field(_isolate_dirs):
    """Pre-M9 days have no `source` field — must surface as None, not crash."""
    data_dir, _ = _isolate_dirs
    _write_day(data_dir, "2026-07-16", headline="a", summary="s", highlights=[], tone="quiet")

    entries = commentary_archive.build_archive_index()

    assert entries[0]["source"] is None


def test_save_archive_index_writes_latest_only(_isolate_dirs):
    _, latest_dir = _isolate_dirs
    commentary_archive.save_archive_index([{"date": "2026-07-20", "headline": "a"}])

    payload = json.loads((latest_dir / "commentary-archive.json").read_text())
    assert payload["entries"] == [{"date": "2026-07-20", "headline": "a"}]
    assert "generated_at" in payload
