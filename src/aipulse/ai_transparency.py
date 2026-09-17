"""AI-engineering transparency panel: the one signal only Langfuse has
(LLM success-vs-template-fallback rate, avg latency) plus signals already
computed locally (tone distribution from commentary.json history, spend from
spend_ledger.py, eval-suite pass rate from eval_runner.py) — bundled into one
small rolling snapshot for the /about page. The Langfuse call fails open like
every other source: a broken or unreachable Langfuse must never block the
pipeline (see tracing.py). The local signals (tone, spend, eval suite) are
pure in-process computation with no external dependency, so a failure there
is a real bug, not a degraded source."""

import json
from datetime import UTC, date, datetime, time, timedelta

from langfuse import Langfuse

from aipulse import spend_ledger
from aipulse.config import (
    AI_TRANSPARENCY_WINDOW_DAYS,
    DATA_DIR,
    LANGFUSE_COMMENTARY_TRACE_NAME,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)
from aipulse.errors import SourceFetchError
from aipulse.eval_runner import run_all_fixtures

# Every commentary call now produces exactly one root observation (no
# children), so each observation row here already corresponds 1:1 to a
# "trace" in the old sense -- no grouping-by-traceId needed. Filtered on
# `traceName` rather than the observation's own `name` since this Langfuse
# project is shared with another codebase's traces (museum-of-hallucinations).
# `type=GENERATION` additionally excludes the wrapping SPAN that the
# pre-migration dual-event ingestion (trace-create + generation-create) left
# under the same trace name -- without it, every day traced before this
# migration double-counts in the trailing 30-day window until it ages out.
_TRACE_NAME_FILTER = json.dumps(
    [{"type": "stringOptions", "column": "traceName", "operator": "any of", "value": [LANGFUSE_COMMENTARY_TRACE_NAME]}]
)


def fetch_commentary_traces(since: date) -> list[dict]:
    """All ai-pulse-commentary observations from `since` onward. Raises
    SourceFetchError on any network/auth failure — caller decides how to
    fail open (see run_ai_transparency in pipeline.py)."""
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        raise SourceFetchError("LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY not set")

    traces: list[dict] = []
    cursor = None
    try:
        client = Langfuse()
        while True:
            response = client.api.observations.get_many(
                fields="core,io,metadata",
                filter=_TRACE_NAME_FILTER,
                type="GENERATION",
                from_start_time=datetime.combine(since, time.min, tzinfo=UTC),
                cursor=cursor,
                limit=100,
            )
            traces.extend({"output": o.output, "metadata": o.metadata} for o in response.data)
            cursor = response.meta.cursor
            if cursor is None:
                break
    except Exception as e:  # noqa: BLE001 - any SDK/network failure maps to SourceFetchError
        raise SourceFetchError(f"Langfuse observations fetch failed: {e}") from e

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
