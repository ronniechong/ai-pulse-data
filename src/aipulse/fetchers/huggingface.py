import requests
from pydantic import ValidationError

from aipulse.config import HF_MODELS_URL, HF_TOKEN, HF_TRENDING_LIMIT
from aipulse.errors import SourceFetchError
from aipulse.schemas import HFModelRow

_TIMEOUT = 30


def fetch_trending_models(limit: int = HF_TRENDING_LIMIT) -> list[HFModelRow]:
    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    params = {"sort": "trendingScore", "direction": "-1", "limit": limit, "full": "true"}
    try:
        resp = requests.get(HF_MODELS_URL, headers=headers, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        rows = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise SourceFetchError(f"HF trending models fetch failed: {e}") from e

    if not isinstance(rows, list) or not rows:
        raise SourceFetchError("HF trending models returned no data")

    try:
        return [HFModelRow.model_validate(r) for r in rows]
    except ValidationError as e:
        raise SourceFetchError(f"HF trending models schema mismatch: {e}") from e
