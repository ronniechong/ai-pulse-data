import requests
from pydantic import ValidationError

from aipulse.config import OPENROUTER_API_KEY, OPENROUTER_APP_RANKINGS_URL, OPENROUTER_RANKINGS_URL
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


def fetch_app_rankings() -> list[OpenRouterAppRow]:
    """Current top-50 apps by token usage (single snapshot, not a date series)."""
    try:
        resp = requests.get(OPENROUTER_APP_RANKINGS_URL, headers=_headers(), timeout=_TIMEOUT)
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
