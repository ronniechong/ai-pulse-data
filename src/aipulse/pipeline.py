import sys
from collections.abc import Callable
from datetime import UTC, date, datetime

from aipulse import history_rollup, notify, publish, quality
from aipulse.commentary import generate_commentary
from aipulse.config import ROLLUP_FILENAMES
from aipulse.errors import SourceFetchError
from aipulse.facts import compute_facts
from aipulse.fetchers import clickpy, huggingface, openrouter
from aipulse.geo_regions import compute_geo_regions
from aipulse.transform import (
    transform_apps,
    transform_hf_trending,
    transform_rankings,
    transform_sdk_geo,
)

SOURCES: list[tuple[str, Callable, Callable]] = [
    ("rankings", openrouter.fetch_rankings_daily, transform_rankings),
    ("apps", openrouter.fetch_app_rankings_with_tags, transform_apps),
    ("hf_trending", huggingface.fetch_trending_models, transform_hf_trending),
    ("sdk_geo", clickpy.fetch_country_downloads, transform_sdk_geo),
]


def run_source(source_key: str, fetch_fn: Callable, transform_fn: Callable, today_str: str) -> dict:
    path = f"data/latest/{publish.SOURCE_FILENAMES[source_key]}"
    try:
        raw = fetch_fn()
        normalized = transform_fn(raw)
        previous = publish.load_previous(source_key)
        violations = quality.evaluate(source_key, normalized, previous)
        if violations:
            raise SourceFetchError("; ".join(violations))
        publish.write_source(source_key, normalized, today_str)
        print(f"[{source_key}] published ok")
        return {"status": "ok", "last_success": today_str, "path": path}
    except SourceFetchError as e:
        prior_entry = publish.load_manifest().get("sources", {}).get(source_key, {})
        last_success = prior_entry.get("last_success")
        print(f"[{source_key}] DEGRADED: {e}", file=sys.stderr)
        notify.notify(
            title=f"AI Pulse: {source_key} degraded",
            message=str(e),
            priority="high",
            tags="warning",
        )
        return {"status": "degraded", "last_success": last_success, "path": path, "error": str(e)}


def run_rankings_history_rollup(today_str: str) -> dict:
    """Extends rankings-history.json with a fresh window fetch (the same
    ~30-day trailing window OpenRouter returns by default). Runs independently
    of the single-day rankings.json publish — a failure here degrades only
    this step; facts/commentary degrade gracefully in turn (see
    run_facts_and_commentary), never the whole pipeline."""
    path = f"data/latest/{ROLLUP_FILENAMES['rankings']}"
    try:
        window_rows = openrouter.fetch_rankings_window()
        if not window_rows:
            raise SourceFetchError("OpenRouter rankings-daily window returned no data")
        existing = history_rollup.load_rollup("rankings")["rows"]
        merged = history_rollup.merge_rankings_rows(existing, window_rows, source="pipeline")
        history_rollup.save_rollup("rankings", merged)
        print("[rankings_history] published ok")
        return {"status": "ok", "last_success": today_str, "path": path}
    except SourceFetchError as e:
        prior_entry = publish.load_manifest().get("sources", {}).get("rankings_history", {})
        last_success = prior_entry.get("last_success")
        print(f"[rankings_history] DEGRADED: {e}", file=sys.stderr)
        notify.notify(
            title="AI Pulse: rankings_history degraded",
            message=str(e),
            priority="high",
            tags="warning",
        )
        return {"status": "degraded", "last_success": last_success, "path": path, "error": str(e)}


def run_geo_regions(today_str: str) -> dict:
    """Derives geo-regions.json from whatever geo-adoption.json + sdk-geo.json
    are currently in data/latest — pure computation, no fetch, never blocks
    the rest of the pipeline (see geo_regions.py)."""
    path = f"data/latest/{publish.SOURCE_FILENAMES['geo_regions']}"
    try:
        geo_adoption = publish.load_previous("geo_adoption")
        sdk_geo = publish.load_previous("sdk_geo")
        normalized = compute_geo_regions(
            geo_adoption, sdk_geo, datetime.now(UTC).isoformat()
        )
        publish.write_source("geo_regions", normalized, today_str)
        print("[geo_regions] published ok")
        return {"status": "ok", "last_success": today_str, "path": path}
    except Exception as e:  # noqa: BLE001 - derived data, must never take down the pipeline
        prior_entry = publish.load_manifest().get("sources", {}).get("geo_regions", {})
        last_success = prior_entry.get("last_success")
        print(f"[geo_regions] DEGRADED: {e}", file=sys.stderr)
        return {"status": "degraded", "last_success": last_success, "path": path, "error": str(e)}


def run_facts_and_commentary(today_str: str, rankings_status: dict, rollup_status: dict) -> dict:
    """Deterministic facts diff + LLM (or template) narration. Never raises —
    any failure here degrades this step alone, never the whole pipeline.

    Gated on the rollup's latest date advancing past the last date facts were
    computed for — NOT on matching today_str. OpenRouter's rankings-daily can
    only report a day once it's fully over (and our cron fires before
    today_str's day ends), so the latest available data is always at least a
    day behind; requiring history[-1][0] == today_str would skip forever."""
    path = f"data/latest/{publish.SOURCE_FILENAMES['facts']}"
    prior_last_success = publish.load_manifest().get("sources", {}).get("facts", {}).get("last_success")

    if rankings_status["status"] != "ok":
        print("[facts] skipped: rankings not published today", file=sys.stderr)
        return {"status": "skipped", "last_success": prior_last_success, "path": path}
    if rollup_status["status"] != "ok":
        print("[facts] skipped: rankings_history rollup not updated today", file=sys.stderr)
        return {"status": "skipped", "last_success": prior_last_success, "path": path}

    try:
        history = history_rollup.rollup_to_history("rankings")
        if not history:
            print("[facts] skipped: rankings history rollup is empty", file=sys.stderr)
            return {"status": "skipped", "last_success": prior_last_success, "path": path}

        latest_date = history[-1][0]
        if latest_date == prior_last_success:
            print(f"[facts] skipped: no new rankings day since {prior_last_success}", file=sys.stderr)
            return {"status": "skipped", "last_success": prior_last_success, "path": path}

        facts = compute_facts(history)
        publish.write_source("facts", facts, today_str)

        commentary = generate_commentary(facts)
        publish.write_source("commentary", commentary, today_str)

        print("[facts] published ok")
        return {"status": "ok", "last_success": latest_date, "path": path}
    except Exception as e:  # noqa: BLE001 - must never take down the pipeline
        print(f"[facts] DEGRADED: {e}", file=sys.stderr)
        notify.notify(
            title="AI Pulse: facts/commentary degraded",
            message=str(e),
            priority="high",
            tags="warning",
        )
        return {"status": "degraded", "last_success": prior_last_success, "path": path, "error": str(e)}


def main() -> None:
    today_str = date.today().isoformat()
    statuses = {
        source_key: run_source(source_key, fetch_fn, transform_fn, today_str)
        for source_key, fetch_fn, transform_fn in SOURCES
    }
    statuses["rankings_history"] = run_rankings_history_rollup(today_str)
    statuses["geo_regions"] = run_geo_regions(today_str)
    statuses["facts"] = run_facts_and_commentary(today_str, statuses["rankings"], statuses["rankings_history"])
    publish.write_manifest(today_str, statuses)

    degraded = [k for k, v in statuses.items() if v["status"] == "degraded"]
    if degraded:
        notify.notify(
            title="AI Pulse: daily pipeline degraded",
            message=f"Degraded sources ({today_str}): {', '.join(degraded)}",
            priority="high",
            tags="warning",
        )
    else:
        notify.notify(
            title="AI Pulse: daily pipeline OK",
            message=f"All sources published for {today_str}",
            priority="default",
            tags="white_check_mark",
        )


if __name__ == "__main__":
    main()
