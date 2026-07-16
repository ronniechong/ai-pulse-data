import csv
from pathlib import Path

from scripts.ingest_occupations import extract_occupation_rows

_HEADER = [
    "date_start", "date_end", "geo_id", "geo_level", "category_name",
    "hierarchy_level", "metric_id", "value", "node_name", "node_external_id",
]


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_HEADER)
        writer.writerows(rows)


def test_extracts_only_global_detailed_occupation_rows_for_latest_period(tmp_path):
    path = tmp_path / "aei.csv"
    _write_csv(
        path,
        [
            # wanted: global, hierarchy_level 0, latest period
            ["2026-05-01", "2026-06-01", "GLOBAL", "global", "soc_occupation", "0", "pct", "5.1", "Writers", "27-3043.00"],
            ["2026-05-01", "2026-06-01", "GLOBAL", "global", "soc_occupation", "0", "collaboration_bucket_automation_pct", "30.0", "Writers", "27-3043.00"],
            ["2026-05-01", "2026-06-01", "GLOBAL", "global", "soc_occupation", "0", "collaboration_bucket_augmentation_pct", "70.0", "Writers", "27-3043.00"],
            # excluded: coarse major group (hierarchy_level 1)
            ["2026-05-01", "2026-06-01", "GLOBAL", "global", "soc_occupation", "1", "pct", "99.0", "Computer and Mathematical", "15-0000"],
            # excluded: country-level, not global
            ["2026-05-01", "2026-06-01", "USA", "country", "soc_occupation", "0", "pct", "99.0", "Writers", "27-3043.00"],
            # excluded: different category
            ["2026-05-01", "2026-06-01", "GLOBAL", "global", "overall", "0", "usage_pct", "99.0", "Overall", ""],
            # excluded: older period
            ["2026-04-01", "2026-05-01", "GLOBAL", "global", "soc_occupation", "0", "pct", "1.0", "Writers", "27-3043.00"],
            # excluded: metric not in WANTED_METRICS
            ["2026-05-01", "2026-06-01", "GLOBAL", "global", "soc_occupation", "0", "ai_autonomy_mean", "2.5", "Writers", "27-3043.00"],
        ],
    )

    occupations, period = extract_occupation_rows(path)

    assert period == {"start": "2026-05-01", "end": "2026-06-01"}
    assert list(occupations.keys()) == ["Writers"]
    row = occupations["Writers"]
    assert row["soc_code"] == "27-3043.00"
    assert row["usage_pct"] == 5.1
    assert row["automation_pct"] == 30.0
    assert row["augmentation_pct"] == 70.0
