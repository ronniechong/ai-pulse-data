from aipulse.schemas import ClickPyCountryRow, HFModelRow, OpenRouterAppRow, OpenRouterRankingRow
from aipulse.transform import (
    transform_apps,
    transform_hf_trending,
    transform_rankings,
    transform_sdk_geo,
)


def test_transform_rankings_sorts_and_computes_share():
    rows = [
        OpenRouterRankingRow(date="2026-07-14", model_permaslug="b", total_tokens=30),
        OpenRouterRankingRow(date="2026-07-14", model_permaslug="a", total_tokens=70),
    ]
    out = transform_rankings(rows)
    assert out["date"] == "2026-07-14"
    assert [m["model"] for m in out["models"]] == ["a", "b"]
    assert out["models"][0]["rank"] == 1
    assert out["models"][0]["token_share"] == 0.7
    assert out["models"][1]["token_share"] == 0.3


def test_transform_apps_sorts_by_rank():
    rows = [
        OpenRouterAppRow(rank=2, app_id=2, app_name="Second", total_tokens=10, total_requests=1),
        OpenRouterAppRow(rank=1, app_id=1, app_name="First", total_tokens=20, total_requests=2),
    ]
    out = transform_apps((rows, {}))
    assert [a["app_name"] for a in out["apps"]] == ["First", "Second"]


def test_transform_apps_attaches_category_tags():
    rows = [OpenRouterAppRow(rank=1, app_id=1, app_name="Cline", total_tokens=20, total_requests=2)]
    out = transform_apps((rows, {1: ["coding", "cli-agent"]}))
    assert out["apps"][0]["categories"] == ["coding", "cli-agent"]


def test_transform_apps_untagged_app_gets_empty_categories():
    rows = [OpenRouterAppRow(rank=1, app_id=1, app_name="Untagged", total_tokens=20, total_requests=2)]
    out = transform_apps((rows, {}))
    assert out["apps"][0]["categories"] == []


def test_transform_hf_trending_assigns_rank_by_input_order():
    rows = [
        HFModelRow(id="org/a", trendingScore=100),
        HFModelRow(id="org/b", trendingScore=50),
    ]
    out = transform_hf_trending(rows)
    assert out["models"][0]["rank"] == 1
    assert out["models"][0]["id"] == "org/a"
    assert out["models"][1]["rank"] == 2


def test_transform_sdk_geo_groups_by_package():
    by_package = {
        "openai": [ClickPyCountryRow(country_code="US", downloads=100)],
        "anthropic": [ClickPyCountryRow(country_code="US", downloads=50)],
    }
    out = transform_sdk_geo(by_package)
    assert out["window_days"] == 30
    assert out["packages"]["openai"]["provider"] == "OpenAI"
    assert out["packages"]["openai"]["countries"] == [{"country_code": "US", "downloads": 100}]
