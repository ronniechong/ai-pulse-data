import json

import pytest

from aipulse.eval_runner import FIXTURES_DIR, run_all_fixtures, run_fixture

FIXTURE_PATHS = sorted(FIXTURES_DIR.glob("*.json"))


def test_at_least_ten_fixtures_exist():
    assert len(FIXTURE_PATHS) >= 10


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_eval_fixture(path):
    fixture = json.loads(path.read_text())
    errors = run_fixture(fixture)
    assert errors == [], f"{path.name}: {errors}"


def test_run_all_fixtures_reports_all_real_fixtures_passing():
    result = run_all_fixtures()
    assert result == {"total": len(FIXTURE_PATHS), "passed": len(FIXTURE_PATHS), "failed": 0, "failures": {}}


def test_run_all_fixtures_counts_a_failing_fixture(tmp_path):
    good = {"facts": {"date": "2026-01-01", "rankings": {"movers": [], "new_entrants": [], "dropouts": [], "records": [], "provider_share": []}}}
    bad = {**good, "expect_tone": "big_day"}  # a quiet-facts payload can never compute as big_day
    (tmp_path / "01_good.json").write_text(json.dumps(good))
    (tmp_path / "02_bad.json").write_text(json.dumps(bad))

    result = run_all_fixtures(tmp_path)
    assert result["total"] == 2
    assert result["passed"] == 1
    assert result["failed"] == 1
    assert "02_bad.json" in result["failures"]
