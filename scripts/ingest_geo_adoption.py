"""One-off / quarterly ingest of the Anthropic Economic Index geographic
release into data/latest/geo-adoption.json (and a dated snapshot).

Not part of the daily pipeline — the Economic Index only ships new
geographic releases every few months. Re-run this manually when a new
release lands (see work-docs/ai-pulse.md architecture summary).

Usage: uv run python scripts/ingest_geo_adoption.py
"""

import csv
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aipulse import publish  # noqa: E402
from aipulse.economic_index import download, find_claude_ai_csv, find_latest_release  # noqa: E402

WANTED_METRICS = {"usage_pct", "usage_per_capita_index"}


def extract_country_rows(csv_path: Path) -> tuple[dict, dict]:
    """Returns (countries_by_code, period) for the latest (date_start, date_end)
    period present among country/overall usage_pct + usage_per_capita_index rows."""
    latest_period: tuple[str, str] | None = None
    matches: list[dict] = []

    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["geo_level"] != "country" or row["category_name"] != "overall":
                continue
            if row["metric_id"] not in WANTED_METRICS:
                continue
            period = (row["date_start"], row["date_end"])
            if latest_period is None or period > latest_period:
                latest_period = period
            matches.append(row)

    if latest_period is None:
        raise RuntimeError("No country-level 'overall' usage_pct/usage_per_capita_index rows found")

    countries: dict[str, dict] = {}
    for row in matches:
        if (row["date_start"], row["date_end"]) != latest_period:
            continue
        entry = countries.setdefault(row["geo_id"], {"country_code": row["geo_id"]})
        entry[row["metric_id"]] = float(row["value"])

    return countries, {"start": latest_period[0], "end": latest_period[1]}


def main() -> None:
    release = find_latest_release()
    print(f"Latest release: {release}")
    csv_relpath = find_claude_ai_csv(release)
    print(f"Downloading {csv_relpath} ...")
    csv_path = download(csv_relpath)
    try:
        countries, period = extract_country_rows(csv_path)
    finally:
        csv_path.unlink(missing_ok=True)

    normalized = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "Anthropic Economic Index (huggingface.co/datasets/Anthropic/EconomicIndex, CC-BY)",
        "release": release,
        "period": period,
        "countries": sorted(countries.values(), key=lambda c: c["country_code"]),
    }

    today_str = date.today().isoformat()
    publish.write_source("geo_adoption", normalized, today_str)
    publish.write_manifest(
        today_str,
        {
            "geo_adoption": {
                "status": "ok",
                "last_success": today_str,
                "path": "data/latest/geo-adoption.json",
            }
        },
    )
    print(
        f"Published {len(normalized['countries'])} countries for period {period['start']}..{period['end']}"
    )


if __name__ == "__main__":
    main()
