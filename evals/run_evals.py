"""CLI entrypoint for the eval suite. See aipulse.eval_runner for the actual
fixture-running logic, which is shared with the AI-transparency panel (M8).

Usage: uv run python evals/run_evals.py
"""

import sys

from aipulse.eval_runner import run_all_fixtures


def main() -> None:
    result = run_all_fixtures()
    print(f"ran {result['total']} eval fixtures")
    if result["failed"]:
        for name, errors in result["failures"].items():
            print(f"FAIL {name}:")
            for e in errors:
                print(f"  - {e}")
        sys.exit(1)
    print("all eval fixtures passed")


if __name__ == "__main__":
    main()
