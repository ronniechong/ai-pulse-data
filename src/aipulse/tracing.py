"""Langfuse tracing for commentary calls, via the `langfuse` SDK.

Previously implemented via direct `requests` calls to the legacy public
ingestion REST API, to keep this repo's dependency footprint small and avoid
coupling to a fast-moving SDK. Migrated to the SDK for Langfuse's v4 rewrite
(2026-09) after the legacy ingestion event shape and the `GET /traces` read
endpoint (see ai_transparency.py) were both deprecated — see work-docs
Decision Log for the full trade-off writeup. Fails open exactly like
notify.py: a broken/unreachable Langfuse must never fail a pipeline run.
"""

from datetime import datetime

from langfuse import Langfuse, propagate_attributes

from aipulse.config import LANGFUSE_COMMENTARY_TRACE_NAME, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY


def trace_commentary_call(
    *,
    prompt_version: str,
    input_facts: dict,
    output: dict | None,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    started_at: datetime,
    ended_at: datetime,
    error: str | None = None,
) -> None:
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        return

    try:
        langfuse = Langfuse()
        with propagate_attributes(
            trace_name=LANGFUSE_COMMENTARY_TRACE_NAME,
            tags=["ai-pulse", prompt_version],
        ):
            generation = langfuse.start_observation(
                name="commentary-generation",
                as_type="generation",
                model=model,
                input=input_facts,
                output=output,
                metadata={"prompt_version": prompt_version, "latency_ms": latency_ms},
                level="ERROR" if error else "DEFAULT",
                status_message=error,
                usage_details={
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens,
                },
                cost_details={"total": cost_usd},
            )
            generation.end(end_time=int(ended_at.timestamp() * 1_000_000_000))
        langfuse.flush()
    except Exception:  # noqa: BLE001 - fails open, must never break a pipeline run
        pass
