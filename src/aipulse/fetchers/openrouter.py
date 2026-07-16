import sys

import requests
from pydantic import ValidationError

from aipulse.config import (
    APP_RANKING_CATEGORIES,
    APP_RANKING_TAG_SUBCATEGORIES,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_RANKINGS_URL,
    OPENROUTER_RANKINGS_URL,
)
from aipulse.errors import SourceFetchError
from aipulse.schemas import OpenRouterAppRow, OpenRouterRankingRow

_TIMEOUT = 30


def _headers() -> dict[str, str]:
    if not OPENROUTER_API_KEY:
        raise SourceFetchError("OPENROUTER_API_KEY is not set")
    return {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}


def fetch_rankings_daily() -> list[OpenRouterRankingRow]:
    """Top-50 models + 'other' for the most recent date in the rankings-daily window."""
    try:
        resp = requests.get(OPENROUTER_RANKINGS_URL, headers=_headers(), timeout=_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise SourceFetchError(f"OpenRouter rankings-daily fetch failed: {e}") from e

    rows = payload.get("data")
    meta = payload.get("meta", {})
    if not isinstance(rows, list) or not rows:
        raise SourceFetchError("OpenRouter rankings-daily returned no data")

    end_date = meta.get("end_date")
    if end_date:
        rows = [r for r in rows if r.get("date") == end_date]
        if not rows:
            raise SourceFetchError(f"No rankings rows found for end_date {end_date}")

    try:
        return [OpenRouterRankingRow.model_validate(r) for r in rows]
    except ValidationError as e:
        raise SourceFetchError(f"OpenRouter rankings-daily schema mismatch: {e}") from e


def fetch_rankings_window(
    start_date: str | None = None, end_date: str | None = None
) -> list[OpenRouterRankingRow]:
    """Unfiltered rankings-daily rows for a date window. A default (no-params)
    call already returns a trailing ~30-day window — this is what the daily
    pipeline uses to self-heal the history rollup for free (no extra request
    beyond the one fetch_rankings_daily already made). Explicit start_date/
    end_date are for the one-off backfill script (max 366-day span per call,
    enforced upstream — data floor is 2025-01-01)."""
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    try:
        resp = requests.get(OPENROUTER_RANKINGS_URL, headers=_headers(), params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise SourceFetchError(f"OpenRouter rankings-daily window fetch failed: {e}") from e

    rows = payload.get("data")
    if not isinstance(rows, list):
        raise SourceFetchError("OpenRouter rankings-daily window returned no data")

    try:
        return [OpenRouterRankingRow.model_validate(r) for r in rows]
    except ValidationError as e:
        raise SourceFetchError(f"OpenRouter rankings-daily window schema mismatch: {e}") from e


def _fetch_app_rankings_raw(params: dict | None = None) -> list[OpenRouterAppRow]:
    try:
        resp = requests.get(
            OPENROUTER_APP_RANKINGS_URL, headers=_headers(), params=params or {}, timeout=_TIMEOUT
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise SourceFetchError(f"OpenRouter app-rankings fetch failed: {e}") from e

    rows = payload.get("data")
    if not isinstance(rows, list) or not rows:
        raise SourceFetchError("OpenRouter app-rankings returned no data")

    try:
        return [OpenRouterAppRow.model_validate(r) for r in rows]
    except ValidationError as e:
        raise SourceFetchError(f"OpenRouter app-rankings schema mismatch: {e}") from e


def fetch_app_rankings() -> list[OpenRouterAppRow]:
    """Current top-50 apps by token usage (single snapshot, not a date series)."""
    return _fetch_app_rankings_raw()


def fetch_app_category_tags() -> dict[int, list[str]]:
    """app_id -> category/subcategory slugs it appears under in their own
    top-50 filtered rankings. Best-effort per slug: one bad filtered request
    degrades only that tag (skipped, logged), never the base apps publish —
    most apps in the base top-50 won't match any slice, which is expected."""
    tags: dict[int, list[str]] = {}
    for slug in APP_RANKING_CATEGORIES:
        param, key = "category", slug
        try:
            rows = _fetch_app_rankings_raw({param: key})
        except SourceFetchError as e:
            print(f"[apps] category tag '{slug}' fetch failed, skipping: {e}", file=sys.stderr)
            continue
        for row in rows:
            tags.setdefault(row.app_id, []).append(slug)
    for slug in APP_RANKING_TAG_SUBCATEGORIES:
        try:
            rows = _fetch_app_rankings_raw({"subcategory": slug})
        except SourceFetchError as e:
            print(f"[apps] subcategory tag '{slug}' fetch failed, skipping: {e}", file=sys.stderr)
            continue
        for row in rows:
            tags.setdefault(row.app_id, []).append(slug)
    return tags


def fetch_app_rankings_with_tags() -> tuple[list[OpenRouterAppRow], dict[int, list[str]]]:
    """Combined fetch used by the daily pipeline: base top-50 (required —
    raises on failure like fetch_app_rankings always has) plus best-effort
    category/subcategory tags (never raises, see fetch_app_category_tags)."""
    return fetch_app_rankings(), fetch_app_category_tags()
