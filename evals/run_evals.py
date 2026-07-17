"""Standalone eval-suite runner — frozen fixtures against the deterministic
facts/template/validation path (no LLM call, no API key needed). See
evals/README.md for why this is mocked-by-default rather than hitting the
real model on every run.

Usage: uv run python evals/run_evals.py
"""

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from aipulse.commentary import render_template_commentary, validate_entities_and_numbers
from aipulse.facts import compute_tone
from aipulse.schemas import CommentaryOutput

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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


def main() -> None:
    fixture_paths = sorted(FIXTURES_DIR.glob("*.json"))
    failures: dict[str, list[str]] = {}

    for path in fixture_paths:
        fixture = json.loads(path.read_text())
        errors = run_fixture(fixture)
        if errors:
            failures[path.name] = errors

    print(f"ran {len(fixture_paths)} eval fixtures")
    if failures:
        for name, errors in failures.items():
            print(f"FAIL {name}:")
            for e in errors:
                print(f"  - {e}")
        sys.exit(1)
    print("all eval fixtures passed")


if __name__ == "__main__":
    main()
