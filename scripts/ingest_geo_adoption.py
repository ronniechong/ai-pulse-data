"""One-off / quarterly ingest of the Anthropic Economic Index geographic
release into data/latest/geo-adoption.json (and a dated snapshot).

Not part of the daily pipeline — the Economic Index only ships new
geographic releases every few months. Re-run this manually when a new
release lands (see work-docs/ai-pulse.md architecture summary).

Usage: uv run python scripts/ingest_geo_adoption.py
"""

import csv
import re
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aipulse import publish  # noqa: E402

HF_DATASET = "Anthropic/EconomicIndex"
HF_API = f"https://huggingface.co/api/datasets/{HF_DATASET}/tree/main"
HF_RESOLVE = f"https://huggingface.co/datasets/{HF_DATASET}/resolve/main"
RELEASE_RE = re.compile(r"^release_\d{4}_\d{2}_\d{2}$")

WANTED_METRICS = {"usage_pct", "usage_per_capita_index"}


def find_latest_release() -> str:
    resp = requests.get(HF_API, timeout=30)
    resp.raise_for_status()
    entries = resp.json()
    releases = sorted(
        e["path"].rsplit("/", 1)[-1]
        for e in entries
        if e["type"] == "directory" and RELEASE_RE.match(e["path"])
    )
    if not releases:
        raise RuntimeError("No release_YYYY_MM_DD folders found in Anthropic/EconomicIndex")
    return releases[-1]


def find_claude_ai_csv(release: str) -> str:
    resp = requests.get(f"{HF_API}/{release}/data", timeout=30)
    resp.raise_for_status()
    for entry in resp.json():
        name = entry["path"].rsplit("/", 1)[-1]
        if name.startswith("aei_claude_ai_") and name.endswith(".csv"):
            return entry["path"]
    raise RuntimeError(f"No aei_claude_ai_*.csv found under {release}/data")


def download(path: str) -> Path:
    url = f"{HF_RESOLVE}/{path}"
    tmp = Path(tempfile.mkstemp(suffix=".csv")[1])
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
    return tmp


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
