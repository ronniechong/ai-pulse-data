"""Deterministic eval-fixture runner. Shared by two callers: the CI-facing
`evals/run_evals.py` CLI, and the AI-transparency panel (M8), which re-runs
this same suite daily as a live "does this exact running code still pass its
own eval fixtures" signal rather than a stale hardcoded badge. No LLM call,
no API key needed — see evals/README.md for why this is mocked-by-default."""

import json
from pathlib import Path

from pydantic import ValidationError

from aipulse.commentary import render_template_commentary, validate_entities_and_numbers
from aipulse.config import REPO_ROOT
from aipulse.facts import compute_tone
from aipulse.schemas import CommentaryOutput

FIXTURES_DIR = REPO_ROOT / "evals" / "fixtures"


def run_fixture(fixture: dict) -> list[str]:
    facts = fixture["facts"]
    errors = []

    expected_tone = fixture.get("expect_tone")
    if expected_tone is not None:
        actual_tone = compute_tone(facts)
        if actual_tone != expected_tone:
            errors.append(f"expected tone {expected_tone!r}, got {actual_tone!r}")

    template = render_template_commentary(facts)
    try:
        CommentaryOutput.model_validate(template)
    except ValidationError as e:
        errors.append(f"template output failed schema validation: {e}")

    self_violations = validate_entities_and_numbers(template, facts)
    if self_violations:
        errors.append(f"template output failed its own entity validation: {self_violations}")

    poisoned = fixture.get("poisoned_output")
    if poisoned is not None:
        violations = validate_entities_and_numbers(poisoned, facts)
        if not violations:
            errors.append("expected poisoned_output to be rejected by entity validation, but it passed clean")

    faithful = fixture.get("faithful_output")
    if faithful is not None:
        violations = validate_entities_and_numbers(faithful, facts)
        if violations:
            errors.append(f"expected faithful_output to pass entity validation clean, but got: {violations}")

    return errors


def run_all_fixtures(fixtures_dir: Path | None = None) -> dict:
    """Runs every *.json fixture in fixtures_dir (defaults to FIXTURES_DIR).
    Returns {"total", "passed", "failed", "failures": {fixture_name: [errors]}}."""
    fixtures_dir = fixtures_dir or FIXTURES_DIR
    fixture_paths = sorted(fixtures_dir.glob("*.json"))
    failures: dict[str, list[str]] = {}
    for path in fixture_paths:
        fixture = json.loads(path.read_text())
        errors = run_fixture(fixture)
        if errors:
            failures[path.name] = errors
    return {
        "total": len(fixture_paths),
        "passed": len(fixture_paths) - len(failures),
        "failed": len(failures),
        "failures": failures,
    }
