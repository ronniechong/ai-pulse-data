"""Aggregates the sdk-geo-history rollup (per-day, per-package, per-country
download counts — 56MB+, ~300k rows and growing) into a small per-region,
per-package daily time series for the SDK-downloads trend chart. The raw
rollup is never served to the client; this recomputes a tiny summary from it
on every pipeline run. See regions.py for the country -> region crosswalk
and its documented gaps (Oceania/Pacific and non-country codes are skipped,
never force-mapped)."""

import sys
from collections import defaultdict

from aipulse.config import SDK_PACKAGES
from aipulse.regions import REGIONS, region_of


def compute_sdk_geo_trend(rollup_rows: list[dict], generated_at: str) -> dict:
    totals: dict[tuple[str, str, str], int] = defaultdict(int)
    skipped: set[str] = set()
    for row in rollup_rows:
        region = region_of(row["country_code"])
        if region is None:
            skipped.add(row["country_code"])
            continue
        totals[(row["date"], region, row["package"])] += row["downloads"]
    if skipped:
        print(f"[sdk_geo_trend] unclassified codes skipped: {sorted(skipped)}", file=sys.stderr)

    series = [
        {"date": d, "region": r, "package": p, "provider": SDK_PACKAGES[p], "downloads": v}
        for (d, r, p), v in sorted(totals.items())
    ]
    return {
        "generated_at": generated_at,
        "source": "derived from sdk-geo-history.json rollup via the static country-to-region crosswalk",
        "regions": list(REGIONS),
        "packages": list(SDK_PACKAGES.keys()),
        "series": series,
    }
