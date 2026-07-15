import json

import pytest

from aipulse import notify, publish
from aipulse.errors import SourceFetchError
from aipulse.pipeline import run_source


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(publish, "DATA_DIR", data_dir)
    monkeypatch.setattr(publish, "LATEST_DIR", data_dir / "latest")
    monkeypatch.setattr(publish, "MANIFEST_PATH", data_dir / "manifest.json")
    monkeypatch.setattr(notify, "notify", lambda *a, **k: None)
    return data_dir


def _good_fetch():
    return {"rows": True}


def _good_transform(_raw):
    # 50 well-formed rankings rows so quality gates pass.
    models = [{"model": f"m{i}", "total_tokens": 1000 - i, "token_share": 0.02} for i in range(50)]
    models[0]["token_share"] = 0.3
    return {"date": "2026-07-14", "models": models}


def test_good_source_publishes_and_updates_manifest(_isolate_data_dir):
    status = run_source("rankings", _good_fetch, _good_transform, "2026-07-16")
    assert status["status"] == "ok"
    assert (publish.LATEST_DIR / "rankings.json").exists()
    assert (publish.DATA_DIR / "2026-07-16" / "rankings.json").exists()


def test_broken_source_keeps_last_good_and_reports_degraded(_isolate_data_dir):
    # First a good run publishes real data, and the pipeline writes the manifest
    # at the end of the run (as pipeline.main() does for every real run) — this
    # is what lets the *next* run recover "last_success" after a failure.
    status = run_source("rankings", _good_fetch, _good_transform, "2026-07-15")
    publish.write_manifest("2026-07-15", {"rankings": status})
    last_good_content = (publish.LATEST_DIR / "rankings.json").read_text()

    # ...then a deliberately broken fetch (simulating a bad URL / upstream outage).
    def broken_fetch():
        raise SourceFetchError("simulated: bad URL")

    status = run_source("rankings", broken_fetch, _good_transform, "2026-07-16")

    assert status["status"] == "degraded"
    assert status["last_success"] == "2026-07-15"
    # latest/ untouched — still the last-good content, not overwritten or deleted.
    assert (publish.LATEST_DIR / "rankings.json").read_text() == last_good_content
    # no dated snapshot written for the failed day.
    assert not (publish.DATA_DIR / "2026-07-16" / "rankings.json").exists()


def test_quality_gate_failure_is_treated_as_degraded(_isolate_data_dir):
    def bad_quality_transform(_raw):
        # Only 2 rows — fails the row-count-bounds gate for rankings.
        return {
            "date": "2026-07-16",
            "models": [{"model": "a", "total_tokens": 10, "token_share": 1.0}],
        }

    status = run_source("rankings", _good_fetch, bad_quality_transform, "2026-07-16")
    assert status["status"] == "degraded"
    assert not (publish.LATEST_DIR / "rankings.json").exists()


def test_manifest_records_per_source_status(_isolate_data_dir):
    run_source("rankings", _good_fetch, _good_transform, "2026-07-16")
    publish.write_manifest(
        "2026-07-16", {"rankings": {"status": "ok", "last_success": "2026-07-16", "path": "x"}}
    )
    manifest = json.loads(publish.MANIFEST_PATH.read_text())
    assert manifest["schema_version"] == 1
    assert manifest["data_version"] == "2026-07-16"
    assert manifest["sources"]["rankings"]["status"] == "ok"
