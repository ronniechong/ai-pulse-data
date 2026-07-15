import requests
from pydantic import ValidationError

from aipulse.config import CLICKHOUSE_URL, SDK_PACKAGES
from aipulse.errors import SourceFetchError
from aipulse.schemas import ClickPyCountryRow

_TIMEOUT = 30
_TABLE = "pypi.pypi_downloads_per_day_by_version_by_country"
_REQUIRED_COLUMNS = {"date", "project", "country_code", "count"}
_WINDOW_DAYS = 30


def _run_query(sql: str) -> dict:
    try:
        resp = requests.get(CLICKHOUSE_URL, params={"user": "play", "query": sql}, timeout=_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise SourceFetchError(f"ClickPy query failed: {e}") from e
    if not resp.ok or resp.text.startswith("Code:"):
        raise SourceFetchError(f"ClickPy query error: {resp.text[:300]}")
    try:
        return resp.json()
    except ValueError as e:
        raise SourceFetchError(f"ClickPy returned non-JSON response: {e}") from e


def _check_schema() -> None:
    """Fail loud if the upstream table's columns have drifted from what we assume."""
    result = _run_query(f"DESCRIBE TABLE {_TABLE} FORMAT JSON")
    columns = {row["name"] for row in result.get("data", [])}
    missing = _REQUIRED_COLUMNS - columns
    if missing:
        raise SourceFetchError(f"ClickPy table {_TABLE} is missing expected columns: {missing}")


def fetch_country_downloads() -> dict[str, list[ClickPyCountryRow]]:
    """Per-country download counts over the trailing window, one query per tracked SDK package."""
    _check_schema()

    results: dict[str, list[ClickPyCountryRow]] = {}
    for package in SDK_PACKAGES:
        sql = (
            f"SELECT country_code, sum(count) AS downloads FROM {_TABLE} "
            f"WHERE project = '{package}' AND date >= today() - {_WINDOW_DAYS} "
            f"GROUP BY country_code ORDER BY downloads DESC FORMAT JSON"
        )
        result = _run_query(sql)
        rows = result.get("data", [])
        try:
            results[package] = [ClickPyCountryRow.model_validate(r) for r in rows]
        except ValidationError as e:
            raise SourceFetchError(f"ClickPy schema mismatch for {package}: {e}") from e

    return results
