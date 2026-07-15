import json
from pathlib import Path

import pytest

from evals.run_evals import run_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "evals" / "fixtures"
FIXTURE_PATHS = sorted(FIXTURES_DIR.glob("*.json"))


def test_at_least_ten_fixtures_exist():
    assert len(FIXTURE_PATHS) >= 10


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_eval_fixture(path):
    fixture = json.loads(path.read_text())
    errors = run_fixture(fixture)
    assert errors == [], f"{path.name}: {errors}"
