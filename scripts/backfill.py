"""One-off historical backfill for M3's racing-bar hero and long-window
(7d/30d) deltas — run locally, NOT part of the daily pipeline. Seeds
data/latest/rankings-history.json and data/latest/sdk-geo-history.json from
OpenRouter's and ClickPy's historical APIs, then you commit + push the
result like any other data change.

Verified live (2026-07-16, see work-docs/ai-pulse.md M2.5 section):
- OpenRouter rankings-daily floor is exactly 2025-01-01; max span per
  request is 366 days, so this needs exactly 2 windowed requests.
- ClickPy has per-day data back to 2023-02-09 for at least one tracked
  package — comfortably covers the 2025-01-01 floor.

Every row is tagged source="backfill". The daily pipeline (source="pipeline")
will naturally overwrite backfilled rows as its own sliding window passes
back over them — see history_rollup.merge_rankings_rows.

Hard rule (M2.5): this script writes ONLY to data/latest/*-history.json.
It must never create a data/YYYY-MM-DD/ folder or touch manifest.json —
those stay exclusively CI-produced, to protect the M1 burn-in provenance.

Usage: uv run python scripts/backfill.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aipulse import history_rollup  # noqa: E402
from aipulse.config import BACKFILL_END_DATE, RANKINGS_HISTORY_FLOOR, SDK_PACKAGES  # noqa: E402
from aipulse.fetchers import clickpy, openrouter  # noqa: E402

# OpenRouter's 366-day-per-request cap means a >366-day span needs multiple
# calls. Split at the floor year's end so any full backfill from
# RANKINGS_HISTORY_FLOOR (2025-01-01) to BACKFILL_END_DATE fits in 2 calls.
_SPLIT_DATE = "2025-12-31"


def backfill_rankings() -> None:
    print(f"Fetching OpenRouter rankings-daily {RANKINGS_HISTORY_FLOOR}..{_SPLIT_DATE} ...")
    window_1 = openrouter.fetch_rankings_window(start_date=RANKINGS_HISTORY_FLOOR, end_date=_SPLIT_DATE)
    print(f"  {len(window_1)} rows")

    next_day = "2026-01-01"
    print(f"Fetching OpenRouter rankings-daily {next_day}..{BACKFILL_END_DATE} ...")
    window_2 = openrouter.fetch_rankings_window(start_date=next_day, end_date=BACKFILL_END_DATE)
    print(f"  {len(window_2)} rows")

    all_rows = window_1 + window_2

    existing = history_rollup.load_rollup("rankings")["rows"]
    merged = history_rollup.merge_rankings_rows(existing, all_rows, source="backfill")
    history_rollup.save_rollup("rankings", merged)

    dates = sorted({r["date"] for r in merged})
    print(f"rankings-history.json: {len(merged)} rows across {len(dates)} days ({dates[0]}..{dates[-1]})")

    # Same window_rows already in hand — no extra fetch, just a different
    # aggregation (per-day total instead of per-day-per-model share).
    existing_totals = history_rollup.load_rollup("rankings_daily_totals")["rows"]
    merged_totals = history_rollup.merge_daily_totals_rows(existing_totals, all_rows, source="backfill")
    history_rollup.save_rollup("rankings_daily_totals", merged_totals)

    totals_dates = sorted({r["date"] for r in merged_totals})
    print(
        f"rankings-totals-history.json: {len(merged_totals)} rows across "
        f"{len(totals_dates)} days ({totals_dates[0]}..{totals_dates[-1]})"
    )


def backfill_sdk_geo() -> None:
    print(f"Fetching ClickPy per-day downloads {RANKINGS_HISTORY_FLOOR}..{BACKFILL_END_DATE} ...")
    by_package = clickpy.fetch_country_downloads_by_day(RANKINGS_HISTORY_FLOOR, BACKFILL_END_DATE)

    new_rows = []
    for package, raw_rows in by_package.items():
        print(f"  {package}: {len(raw_rows)} (date, country) rows")
        for r in raw_rows:
            new_rows.append(
                {
                    "date": r["date"],
                    "package": package,
                    "provider": SDK_PACKAGES[package],
                    "country_code": r["country_code"],
                    "downloads": int(r["downloads"]),
                }
            )

    existing = history_rollup.load_rollup("sdk_geo")["rows"]
    merged = history_rollup.merge_sdk_geo_rows(existing, new_rows, source="backfill")
    history_rollup.save_rollup("sdk_geo", merged)

    dates = sorted({r["date"] for r in merged})
    print(f"sdk-geo-history.json: {len(merged)} rows across {len(dates)} days ({dates[0]}..{dates[-1]})")


def main() -> None:
    backfill_rankings()
    backfill_sdk_geo()
    print("Backfill complete. Review data/latest/*-history.json, then commit + push.")


if __name__ == "__main__":
    main()
