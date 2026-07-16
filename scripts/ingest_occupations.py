"""One-off / quarterly ingest of the Anthropic Economic Index's occupation
(soc_occupation) usage split into data/latest/occupations.json.

Same release cadence and CSV as scripts/ingest_geo_adoption.py — re-run
manually when a new Economic Index release lands.

Live-probed 2026-07-16 against release_2026_06_26 (see work-docs M2.6):
category_name='soc_occupation', geo_level='global', hierarchy_level='0' is
the detailed-occupation granularity (718 SOC titles; hierarchy_level='1' is
22 coarse major groups instead — not what the design's per-occupation panel
wants). metric_id='pct' is usage share; 'collaboration_bucket_automation_pct'
/'_augmentation_pct' are the automation-vs-augmentation split the M3 design
mocks. The doc's original metric-name guess was unverified before this
probe — confirmed correct.

Usage: uv run python scripts/ingest_occupations.py
"""

import csv
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aipulse import publish  # noqa: E402
from aipulse.economic_index import download, find_claude_ai_csv, find_latest_release  # noqa: E402

WANTED_METRICS = {"pct", "collaboration_bucket_automation_pct", "collaboration_bucket_augmentation_pct"}

# M2.6 decision: surface more than the design's illustrative 8 so the web
# client has room to choose a display count; ranked by real usage share.
TOP_N = 20


def extract_occupation_rows(csv_path: Path) -> tuple[dict, dict]:
    """Returns (occupations_by_name, period) for the latest (date_start, date_end)
    period present among global soc_occupation detailed-occupation rows."""
    latest_period: tuple[str, str] | None = None
    matches: list[dict] = []

    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (
                row["category_name"] != "soc_occupation"
                or row["geo_level"] != "global"
                or row["hierarchy_level"] != "0"
            ):
                continue
            if row["metric_id"] not in WANTED_METRICS:
                continue
            period = (row["date_start"], row["date_end"])
            if latest_period is None or period > latest_period:
                latest_period = period
            matches.append(row)

    if latest_period is None:
        raise RuntimeError("No global soc_occupation detailed-occupation rows found")

    occupations: dict[str, dict] = {}
    metric_key = {
        "pct": "usage_pct",
        "collaboration_bucket_automation_pct": "automation_pct",
        "collaboration_bucket_augmentation_pct": "augmentation_pct",
    }
    for row in matches:
        if (row["date_start"], row["date_end"]) != latest_period:
            continue
        entry = occupations.setdefault(
            row["node_name"], {"name": row["node_name"], "soc_code": row["node_external_id"]}
        )
        entry[metric_key[row["metric_id"]]] = float(row["value"])

    return occupations, {"start": latest_period[0], "end": latest_period[1]}


def main() -> None:
    release = find_latest_release()
    print(f"Latest release: {release}")
    csv_relpath = find_claude_ai_csv(release)
    print(f"Downloading {csv_relpath} ...")
    csv_path = download(csv_relpath)
    try:
        occupations, period = extract_occupation_rows(csv_path)
    finally:
        csv_path.unlink(missing_ok=True)

    ranked = sorted(occupations.values(), key=lambda o: o.get("usage_pct", 0.0), reverse=True)[:TOP_N]

    normalized = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "Anthropic Economic Index (huggingface.co/datasets/Anthropic/EconomicIndex, CC-BY)",
        "release": release,
        "period": period,
        "occupations": ranked,
    }

    today_str = date.today().isoformat()
    publish.write_source("occupations", normalized, today_str)
    publish.write_manifest(
        today_str,
        {
            "occupations": {
                "status": "ok",
                "last_success": today_str,
                "path": "data/latest/occupations.json",
            }
        },
    )
    print(f"Published {len(ranked)} occupations for period {period['start']}..{period['end']}")


if __name__ == "__main__":
    main()
