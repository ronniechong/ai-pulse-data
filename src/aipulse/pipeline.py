import sys
from collections.abc import Callable
from datetime import date

from aipulse import notify, publish, quality
from aipulse.commentary import generate_commentary
from aipulse.errors import SourceFetchError
from aipulse.facts import compute_facts
from aipulse.fetchers import clickpy, huggingface, openrouter
from aipulse.transform import (
    transform_apps,
    transform_hf_trending,
    transform_rankings,
    transform_sdk_geo,
)

SOURCES: list[tuple[str, Callable, Callable]] = [
    ("rankings", openrouter.fetch_rankings_daily, transform_rankings),
    ("apps", openrouter.fetch_app_rankings, transform_apps),
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


def run_facts_and_commentary(today_str: str, rankings_status: dict) -> dict:
    """Deterministic facts diff + LLM (or template) narration. Never raises —
    any failure here degrades this step alone, never the whole pipeline."""
    path = f"data/latest/{publish.SOURCE_FILENAMES['facts']}"
    if rankings_status["status"] != "ok":
        print("[facts] skipped: rankings not published today", file=sys.stderr)
        return {"status": "skipped", "last_success": None, "path": path}

    try:
        history = publish.load_history("rankings", up_to_date=today_str)
        if not history or history[-1][0] != today_str:
            print("[facts] skipped: no rankings snapshot for today in history", file=sys.stderr)
            return {"status": "skipped", "last_success": None, "path": path}

        facts = compute_facts(history)
        publish.write_source("facts", facts, today_str)

        commentary = generate_commentary(facts)
        publish.write_source("commentary", commentary, today_str)

        print("[facts] published ok")
        return {"status": "ok", "last_success": today_str, "path": path}
    except Exception as e:  # noqa: BLE001 - must never take down the pipeline
        print(f"[facts] DEGRADED: {e}", file=sys.stderr)
        notify.notify(
            title="AI Pulse: facts/commentary degraded",
            message=str(e),
            priority="high",
            tags="warning",
        )
        return {"status": "degraded", "last_success": None, "path": path, "error": str(e)}


def main() -> None:
    today_str = date.today().isoformat()
    statuses = {
        source_key: run_source(source_key, fetch_fn, transform_fn, today_str)
        for source_key, fetch_fn, transform_fn in SOURCES
    }
    statuses["facts"] = run_facts_and_commentary(today_str, statuses["rankings"])
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
