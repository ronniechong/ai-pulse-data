"""AI-engineering transparency panel (M8): the one signal only Langfuse has
(LLM success-vs-template-fallback rate, avg latency) plus signals already
computed locally (tone distribution from commentary.json history, spend from
spend_ledger.py, eval-suite pass rate from eval_runner.py) — bundled into one
small rolling snapshot for the /about page. The Langfuse call fails open like
every other source: a broken or unreachable Langfuse must never block the
pipeline (see tracing.py). The local signals (tone, spend, eval suite) are
pure in-process computation with no external dependency, so a failure there
is a real bug, not a degraded source."""

import json
from datetime import date, timedelta

import requests

from aipulse import spend_ledger
from aipulse.config import (
    AI_TRANSPARENCY_WINDOW_DAYS,
    DATA_DIR,
    LANGFUSE_COMMENTARY_TRACE_NAME,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
    LANGFUSE_TRACES_PATH,
)
from aipulse.errors import SourceFetchError
from aipulse.eval_runner import run_all_fixtures

_TIMEOUT = 15


def fetch_commentary_traces(since: date) -> list[dict]:
    """All ai-pulse-commentary traces from `since` onward. Raises
    SourceFetchError on any network/auth failure — caller decides how to
    fail open (see run_ai_transparency in pipeline.py)."""
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        raise SourceFetchError("LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY not set")

    traces: list[dict] = []
    page = 1
    try:
        while True:
            resp = requests.get(
                f"{LANGFUSE_HOST}{LANGFUSE_TRACES_PATH}",
                params={
                    "name": LANGFUSE_COMMENTARY_TRACE_NAME,
                    "fromTimestamp": f"{since.isoformat()}T00:00:00Z",
                    "page": page,
                    "limit": 100,
                },
                auth=(LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
            traces.extend(payload.get("data", []))
            if page >= payload.get("meta", {}).get("totalPages", 1):
                break
            page += 1
    except (requests.RequestException, ValueError) as e:
        raise SourceFetchError(f"Langfuse traces fetch failed: {e}") from e

    return traces


def compute_llm_reliability(traces: list[dict]) -> dict:
    """Attempt-level (not day-level) classification: a trace is a success if
    it carries a non-null `output`, a fallback attempt otherwise (see
    commentary.py — every OpenRouter call attempt is traced individually,
    including retries; the template fallback itself is never traced since
    it makes no LLM call). A day with COMMENTARY_MAX_RETRIES > 0 can contain
    more than one trace, so this rate is "share of attempts that produced
    usable output," not "share of days the LLM was used" — documented as a
    caveat in METRICS.md."""
    total = len(traces)
    success = sum(1 for t in traces if t.get("output") is not None)
    fallback = total - success
    latencies = [
        t["metadata"]["latency_ms"]
        for t in traces
        if isinstance(t.get("metadata"), dict) and isinstance(t["metadata"].get("latency_ms"), (int, float))
    ]
    return {
        "attempts_checked": total,
        "success_count": success,
        "fallback_count": fallback,
        "success_rate": round(success / total, 4) if total else None,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
    }


def compute_tone_distribution(window_days: int) -> dict:
    """Tallies `commentary.json`'s `tone` field across the trailing window
    from local dated data/ folders — no Langfuse call needed, this data
    already exists on disk for every real pipeline day."""
    counts = {"quiet": 0, "notable": 0, "big_day": 0}
    days_checked = 0
    today = date.today()
    for offset in range(window_days):
        day = today - timedelta(days=offset)
        path = DATA_DIR / day.isoformat() / "commentary.json"
        if not path.exists():
            continue
        days_checked += 1
        tone = json.loads(path.read_text()).get("tone")
        if tone in counts:
            counts[tone] += 1
    return {**counts, "days_checked": days_checked}


def compute_eval_suite_health() -> dict:
    """Re-runs the local eval-fixture suite (aipulse.eval_runner) as part of
    the daily production pipeline — a live "does this exact running code
    still pass its own eval fixtures" signal rather than a hardcoded badge
    that could go stale as fixtures are added or removed. No network call,
    deterministic, sub-second (see evals/README.md)."""
    result = run_all_fixtures()
    return {"total": result["total"], "passed": result["passed"], "failed": result["failed"]}


def compute_spend(ledger: dict) -> dict:
    lifetime = spend_ledger.lifetime_totals(ledger)
    cost_per_generation = round(lifetime["cost_usd"] / lifetime["calls"], 6) if lifetime["calls"] else None
    return {
        "month_to_date_usd": spend_ledger.month_to_date_cost(ledger),
        "lifetime_usd": lifetime["cost_usd"],
        "lifetime_calls": lifetime["calls"],
        "cost_per_generation_usd": cost_per_generation,
    }


def compute_ai_transparency(generated_at: str) -> dict:
    window_days = AI_TRANSPARENCY_WINDOW_DAYS
    since = date.today() - timedelta(days=window_days)
    traces = fetch_commentary_traces(since)
    ledger = spend_ledger.load_ledger()

    return {
        "generated_at": generated_at,
        "window_days": window_days,
        "source": (
            "LLM reliability from Langfuse ai-pulse-commentary traces; "
            "tone distribution from local commentary.json history; "
            "spend from spend-ledger.json; eval-suite health from a live "
            "re-run of evals/fixtures"
        ),
        "llm_reliability": compute_llm_reliability(traces),
        "tone_distribution": compute_tone_distribution(window_days),
        "spend": compute_spend(ledger),
        "eval_suite": compute_eval_suite_health(),
    }
