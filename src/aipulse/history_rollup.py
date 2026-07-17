"""Rolling history rollups (rankings-history.json, sdk-geo-history.json).

Unlike the per-day data/YYYY-MM-DD/ snapshots, these are cumulative files
living only in data/latest/ — see M2.5 in work-docs for the provenance
rules (backfill seeds them once; the daily pipeline extends rankings-history
forward for free using the window fetch_rankings_window already returns).
"""

import json
from datetime import UTC, datetime

from aipulse.config import LATEST_DIR, ROLLUP_FILENAMES
from aipulse.schemas import OpenRouterRankingRow


def _rollup_path(source_key: str):
    return LATEST_DIR / ROLLUP_FILENAMES[source_key]


def load_rollup(source_key: str) -> dict:
    path = _rollup_path(source_key)
    if not path.exists():
        return {"generated_at": None, "rows": []}
    return json.loads(path.read_text())


def save_rollup(source_key: str, rows: list[dict]) -> None:
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(UTC).isoformat(), "rows": rows}
    _rollup_path(source_key).write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def _rank_and_share_by_date(rows: list[OpenRouterRankingRow]) -> list[dict]:
    """Group raw (date, model, total_tokens) rows by date, then rank + compute
    token_share within each date — same logic as transform.transform_rankings
    but applied per-day across a whole window instead of a single day."""
    by_date: dict[str, list[OpenRouterRankingRow]] = {}
    for row in rows:
        by_date.setdefault(row.date.isoformat(), []).append(row)

    out = []
    for date_str, day_rows in by_date.items():
        day_rows = sorted(day_rows, key=lambda r: r.total_tokens, reverse=True)
        total = sum(r.total_tokens for r in day_rows) or 1
        for i, r in enumerate(day_rows):
            out.append(
                {
                    "date": date_str,
                    "model": r.model_permaslug,
                    "rank": i + 1,
                    "token_share": round(r.total_tokens / total, 6),
                }
            )
    return out


def merge_rankings_rows(
    existing_rows: list[dict], new_window_rows: list[OpenRouterRankingRow], source: str
) -> list[dict]:
    """Merge a freshly-fetched window into the existing rollup rows. Newer
    fetches always win on (date, model) conflicts: this lets the rollup
    self-heal (a re-fetched date supersedes a stale one) and lets
    "pipeline"-sourced rows naturally overwrite "backfill" ones as the daily
    ~30-day window slides back over previously-backfilled dates."""
    merged: dict[tuple[str, str], dict] = {(r["date"], r["model"]): r for r in existing_rows}
    for row in _rank_and_share_by_date(new_window_rows):
        row["source"] = source
        merged[(row["date"], row["model"])] = row
    return sorted(merged.values(), key=lambda r: (r["date"], r["rank"]))


def merge_sdk_geo_rows(existing_rows: list[dict], new_rows: list[dict], source: str) -> list[dict]:
    """Flat (date, package, country_code, downloads) rows, no rank/share
    computation needed. Newer fetches win on (date, package, country_code)
    conflicts, same self-healing behavior as merge_rankings_rows — lets the
    daily pipeline's trailing-window re-fetch correct late-arriving ClickPy
    data, and lets "pipeline"-sourced rows naturally supersede "backfill"
    ones as the window slides forward."""
    merged: dict[tuple[str, str, str], dict] = {
        (r["date"], r["package"], r["country_code"]): r for r in existing_rows
    }
    for row in new_rows:
        row = dict(row)
        row["source"] = source
        merged[(row["date"], row["package"], row["country_code"])] = row
    return sorted(merged.values(), key=lambda r: (r["date"], r["package"], -r["downloads"]))


def rollup_to_history(source_key: str) -> list[tuple[str, dict]]:
    """Reshape the rollup into the (date_str, {"models": [...]}) format
    facts.compute_facts already expects."""
    rollup = load_rollup(source_key)
    by_date: dict[str, list[dict]] = {}
    for row in rollup["rows"]:
        by_date.setdefault(row["date"], []).append(
            {"rank": row["rank"], "model": row["model"], "token_share": row["token_share"]}
        )
    return [
        (date_str, {"models": sorted(models, key=lambda m: m["rank"])})
        for date_str, models in sorted(by_date.items())
    ]
