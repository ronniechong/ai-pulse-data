from datetime import date as date_type

from pydantic import BaseModel, ConfigDict


class OpenRouterRankingRow(BaseModel):
    """One (date, model) row from GET /api/v1/datasets/rankings-daily.

    total_tokens comes back as a numeric string over the wire (exceeds
    JS safe-integer range) — pydantic coerces it to int here.
    """

    model_config = ConfigDict(extra="ignore")

    date: date_type
    model_permaslug: str
    total_tokens: int


class OpenRouterAppRow(BaseModel):
    """One app row from GET /api/v1/datasets/app-rankings.

    This is a single current-window top-50 snapshot (rank-ordered), not a
    per-day series — unlike rankings-daily there's no `date` field per row.
    """

    model_config = ConfigDict(extra="ignore")

    rank: int
    app_id: int
    app_name: str
    total_tokens: int
    total_requests: int


class HFModelRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    author: str | None = None
    downloads: int = 0
    downloadsAllTime: int | None = None
    likes: int = 0
    trendingScore: int = 0
    pipeline_tag: str | None = None
    library_name: str | None = None


class ClickPyCountryRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    country_code: str
    downloads: int
