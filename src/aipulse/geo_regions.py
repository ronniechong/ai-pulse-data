"""Aggregates geo-adoption.json + sdk-geo.json into the 8-region bucket
grid the M3 design's geo panel needs. See regions.py for the country ->
region crosswalk and its documented gaps (Oceania/Pacific and non-country
codes are skipped with a logged warning, never force-mapped).

Pure derivation over whatever is currently in data/latest/ — geo-adoption
only updates quarterly (scripts/ingest_geo_adoption.py) while sdk-geo
updates daily, so this recomputes from both on every pipeline run rather
than depending on either "publishing today"."""

import sys

from aipulse.regions import REGIONS, region_of


def _aggregate_adoption(geo_adoption: dict) -> dict[str, float]:
    totals: dict[str, float] = dict.fromkeys(REGIONS, 0.0)
    skipped: set[str] = set()
    for country in geo_adoption["countries"]:
        region = region_of(country["country_code"])
        if region is None:
            skipped.add(country["country_code"])
            continue
        totals[region] += country.get("usage_pct", 0.0)
    if skipped:
        print(f"[geo_regions] adoption: unclassified codes skipped: {sorted(skipped)}", file=sys.stderr)
    return totals


def _aggregate_downloads(sdk_geo: dict) -> dict[str, float]:
    totals: dict[str, float] = dict.fromkeys(REGIONS, 0.0)
    skipped: set[str] = set()
    for package in sdk_geo["packages"].values():
        for country in package["countries"]:
            region = region_of(country["country_code"])
            if region is None:
                skipped.add(country["country_code"])
                continue
            totals[region] += country["downloads"]
    if skipped:
        print(f"[geo_regions] downloads: unclassified codes skipped: {sorted(skipped)}", file=sys.stderr)
    return totals


def compute_geo_regions(geo_adoption: dict | None, sdk_geo: dict | None, generated_at: str) -> dict:
    """Either input may be None (geo-adoption not ingested yet, or sdk_geo
    degraded today) — that toggle's region list is simply empty, not an
    error; the other toggle still publishes."""
    adoption_totals = _aggregate_adoption(geo_adoption) if geo_adoption else None
    download_totals = _aggregate_downloads(sdk_geo) if sdk_geo else None

    return {
        "generated_at": generated_at,
        "source": (
            "derived from geo-adoption.json (Anthropic Economic Index, CC-BY) "
            "+ sdk-geo.json (ClickPy) via a static country-to-region crosswalk"
        ),
        "regions": {
            "adoption": (
                [{"region": r, "value": round(adoption_totals[r], 4)} for r in REGIONS]
                if adoption_totals is not None
                else []
            ),
            "downloads": (
                [{"region": r, "value": int(download_totals[r])} for r in REGIONS]
                if download_totals is not None
                else []
            ),
        },
    }
