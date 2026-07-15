from datetime import UTC, datetime

from aipulse.config import SDK_PACKAGES
from aipulse.schemas import ClickPyCountryRow, HFModelRow, OpenRouterAppRow, OpenRouterRankingRow


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def transform_rankings(rows: list[OpenRouterRankingRow]) -> dict:
    rows = sorted(rows, key=lambda r: r.total_tokens, reverse=True)
    total = sum(r.total_tokens for r in rows) or 1
    return {
        "generated_at": _now_iso(),
        "date": rows[0].date.isoformat(),
        "source": "OpenRouter (openrouter.ai/rankings)",
        "models": [
            {
                "rank": i + 1,
                "model": r.model_permaslug,
                "total_tokens": r.total_tokens,
                "token_share": round(r.total_tokens / total, 6),
            }
            for i, r in enumerate(rows)
        ],
    }


def transform_apps(rows: list[OpenRouterAppRow]) -> dict:
    rows = sorted(rows, key=lambda r: r.rank)
    return {
        "generated_at": _now_iso(),
        "source": "OpenRouter (openrouter.ai/apps)",
        "apps": [
            {
                "rank": r.rank,
                "app_id": r.app_id,
                "app_name": r.app_name,
                "total_tokens": r.total_tokens,
                "total_requests": r.total_requests,
            }
            for r in rows
        ],
    }


def transform_hf_trending(rows: list[HFModelRow]) -> dict:
    return {
        "generated_at": _now_iso(),
        "source": "Hugging Face Hub (huggingface.co/models?sort=trending)",
        "models": [
            {
                "rank": i + 1,
                "id": r.id,
                "author": r.author,
                "downloads": r.downloads,
                "downloads_all_time": r.downloadsAllTime,
                "likes": r.likes,
                "trending_score": r.trendingScore,
                "pipeline_tag": r.pipeline_tag,
                "library_name": r.library_name,
            }
            for i, r in enumerate(rows)
        ],
    }


def transform_sdk_geo(by_package: dict[str, list[ClickPyCountryRow]]) -> dict:
    return {
        "generated_at": _now_iso(),
        "source": "ClickPy / PyPI downloads (clickpy.clickhouse.com)",
        "window_days": 30,
        "packages": {
            package: {
                "provider": SDK_PACKAGES[package],
                "countries": [
                    {"country_code": row.country_code, "downloads": row.downloads} for row in rows
                ],
            }
            for package, rows in by_package.items()
        },
    }
