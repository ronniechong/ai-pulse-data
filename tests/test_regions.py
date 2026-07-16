from aipulse.geo_regions import compute_geo_regions
from aipulse.regions import REGIONS, region_of


def test_region_of_handles_alpha2_and_alpha3():
    assert region_of("US") == "North America"
    assert region_of("USA") == "North America"
    assert region_of("in") == "South Asia"  # case-insensitive


def test_region_of_returns_none_for_unclassified_codes():
    # Oceania has no bucket in the design's 8 regions (documented gap), and
    # 'EU' is ClickPy's aggregate code, not a real country.
    assert region_of("AU") is None
    assert region_of("AUS") is None
    assert region_of("EU") is None
    assert region_of("XX") is None


def test_compute_geo_regions_aggregates_by_region():
    geo_adoption = {
        "countries": [
            {"country_code": "USA", "usage_pct": 10.0},
            {"country_code": "CAN", "usage_pct": 5.0},
            {"country_code": "DEU", "usage_pct": 3.0},
            {"country_code": "AUS", "usage_pct": 999.0},  # unclassified, must not leak in
        ]
    }
    out = compute_geo_regions(geo_adoption, None, "2026-07-16T00:00:00+00:00")

    adoption = {r["region"]: r["value"] for r in out["regions"]["adoption"]}
    assert adoption["North America"] == 15.0
    assert adoption["Europe"] == 3.0
    assert sum(adoption.values()) == 18.0  # AUS's 999 never gets counted anywhere
    assert out["regions"]["downloads"] == []


def test_compute_geo_regions_sums_across_all_sdk_packages():
    sdk_geo = {
        "packages": {
            "openai": {"countries": [{"country_code": "US", "downloads": 100}]},
            "anthropic": {"countries": [{"country_code": "US", "downloads": 50}]},
        }
    }
    out = compute_geo_regions(None, sdk_geo, "2026-07-16T00:00:00+00:00")

    downloads = {r["region"]: r["value"] for r in out["regions"]["downloads"]}
    assert downloads["North America"] == 150
    assert out["regions"]["adoption"] == []


def test_all_eight_design_regions_always_present_when_data_exists():
    geo_adoption = {"countries": [{"country_code": "USA", "usage_pct": 1.0}]}
    out = compute_geo_regions(geo_adoption, None, "2026-07-16T00:00:00+00:00")
    assert {r["region"] for r in out["regions"]["adoption"]} == set(REGIONS)
